"""Report boundary validation, snapshot ownership, and pagination contracts."""

from datetime import date, datetime, timedelta
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pymysql

from mycount.activity.ReadReports import ReadReports
from mycount.entity.ReportOptions import ReportOptions
from mycount.entity.Report import Report
from mycount.interface.ReportQuery import ReportQuery
from mycount.server.ControlPages import ControlPages


class ReportTests(unittest.TestCase):
    def test_range_timezone_and_cursor_validation(self):
        query = dict(start=['2026-03-07'], end=['2026-03-10'], timezone=['America/Toronto'])
        options = ReportQuery.resolve(query)
        self.assertEqual(options.start, date(2026, 3, 7))
        self.assertEqual(options.end, date(2026, 3, 10))
        for changes in [dict(start=['2026-03-11']), dict(start=['2025-01-01']),
                        dict(start=['2026-02-30']), dict(end=['9999-12-31']),
                        dict(timezone=['Missing/Zone']), dict(timezone=['../UTC']),
                        dict(before=['2026-03-10T00:00:00+00:00,1']), dict(before=['bad']),
                        dict(before=['2026-03-10,0']), dict(before=['2026-03-10,18446744073709551616']),
                        dict(start=['2026-03-07', '2026-03-08']), dict(exclude_bots=['bad']),
                        dict(site=['']), dict(site=['a', 'b']), dict(site=['%']),
                        dict(site=['a' * 101]), dict(site=['<script>'])]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                ReportQuery.resolve({**query, **changes})
        options = ReportQuery.resolve(dict(start=['2025-01-01'], end=['2026-01-01']))
        self.assertEqual(len(options.day_ranges()), 366)
        self.assertEqual((ReportQuery.resolve({}).end - ReportQuery.resolve({}).start).days, 29)

    def test_site_defaults_and_selection_render_on_each_report_page(self):
        pages = ControlPages()
        for site in ('*', 'example', 'missing'):
            options = ReportQuery.resolve({'site': [site]})
            report = Report(options, [], None, available_sites=['example', 'other'])
            self.assertEqual(ReportQuery.resolve(parse_qs(urlsplit(ReportQuery.link('/metrics', options)).query)).site, site)
            for render in (pages.render, pages.visitor_map, pages.marketing):
                with self.subTest(site=site, page=render.__name__):
                    html = render(report).decode()
                    self.assertIn('<select name="site">', html)
                    self.assertIn(f'<option value="{site}" selected>{site}</option>', html)
                    self.assertIn('<option value="other">other</option>', html)
        self.assertEqual(ReportQuery.resolve({}).site, '*')

    def test_local_day_boundaries_include_dst_and_fractional_offsets(self):
        for day, zone, hours, start in [
            (date(2026, 3, 8), 'America/Toronto', 23, datetime(2026, 3, 8, 5)),
            (date(2026, 11, 1), 'America/Toronto', 25, datetime(2026, 11, 1, 4)),
            (date(2026, 3, 8), 'Asia/Kathmandu', 24, datetime(2026, 3, 7, 18, 15)),
        ]:
            with self.subTest(zone=zone, day=day):
                ranges = ReportOptions(day, day, zone).day_ranges()
                self.assertEqual(ranges[0][1], start)
                self.assertEqual(ranges[0][2] - ranges[0][1], timedelta(hours=hours))

    @patch('mycount.activity.ReadReports.DbMgr')
    def test_metrics_snapshot_bounds_recent_rows_and_preserves_filters_in_links(self, factory):
        timestamp = datetime(2026, 3, 8, 12)
        rows = [dict(page_view_id=index, received_at=timestamp, country_code=None,
                     city_name=None, url=f'https://example.com/{index}') for index in range(51, 0, -1)]
        factory.return_value.query.side_effect = [[], [], [], rows, [],
                                                  [dict(language_tag='en-CA', page_views=5000)],
                                                  [dict(day='2026-03-08', page_views=5000)],
                                                  [dict(first_visit_at=timestamp)], [dict(site="example"), dict(site="other")]]
        options = ReportOptions(date(2026, 3, 8), date(2026, 3, 8), 'America/Toronto', site='example')
        report = ReadReports().metrics(options)
        self.assertEqual(len(report.recent), 50)
        self.assertEqual(report.older, (timestamp, 2))
        self.assertEqual(report.daily[0]['page_views'], 5000)
        self.assertEqual(report.languages, [dict(language_tag='en-CA', page_views=5000)])
        factory.return_value.transaction.assert_called_once_with(read_only=True)
        factory.return_value.close.assert_called_once()
        calls = factory.return_value.query.call_args_list
        self.assertEqual(calls[3].args[1][-1], 51)
        for call in calls[:6]:
            self.assertIn(datetime(2026, 3, 8, 5), call.args[1])
            self.assertIn(datetime(2026, 3, 9, 4), call.args[1])
        query = parse_qs(urlsplit(ReportQuery.link('/metrics', options, report.older)).query)
        self.assertEqual(ReportQuery.resolve(query).before, report.older)
        self.assertEqual(query['timezone'], ['America/Toronto'])
        self.assertEqual(query['site'], ['example'])
        self.assertEqual(report.available_sites, ['example', 'other'])
        for call in calls[:7]:
            self.assertIn('site_page.site = %s', call.args[0])
            self.assertIn('example', call.args[1])
        html = ControlPages().render(report).decode()
        recent_summary = html.split('<span>Recent Visits</span>', 1)[1].split('</summary>', 1)[0]
        self.assertIn('Older visits', recent_summary)
        self.assertIn('href="/metrics?', recent_summary)
        self.assertIn('<a href="/">Map</a>', html)
        self.assertIn('"page_views": 5000', html)
        self.assertIn('<option value="example" selected>example</option>', html)
        self.assertIn('<option value="other">other</option>', html)
        self.assertNotIn('const timestamps', html)

    @patch('mycount.activity.ReadReports.DbMgr')
    def test_marketing_uses_daily_totals_without_fetching_individual_visits(self, factory):
        factory.return_value.query.side_effect = [[], [dict(day='2026-03-08', page_views=0)],
                                                  [dict(first_visit_at=None)], [dict(site="example")]]
        options = ReportOptions(date(2026, 3, 8), date(2026, 3, 8), 'UTC', site='example')
        report = ReadReports().marketing(options)
        self.assertEqual(report.daily, [dict(day='2026-03-08', page_views=0)])
        daily_call = factory.return_value.query.call_args_list[1]
        self.assertIn('site_page.site = %s', daily_call.args[0])
        self.assertIn('example', daily_call.args[1])
        self.assertEqual(report.available_sites, ['example'])
        self.assertNotIn('JOIN pages', daily_call.args[0])
        factory.return_value.transaction.assert_called_once_with(read_only=True)
        factory.return_value.close.assert_called_once()

    @patch('mycount.activity.ReadReports.DbMgr')
    def test_report_query_failure_closes_connection_and_leaves_transaction(self, factory):
        error = pymysql.OperationalError(2013, 'offline')
        factory.return_value.query.side_effect = error
        options = ReportOptions(date(2026, 3, 8), date(2026, 3, 8), 'UTC')
        with self.assertRaises(pymysql.OperationalError) as raised:
            ReadReports().metrics(options)
        self.assertIs(raised.exception, error)
        factory.return_value.transaction.return_value.__exit__.assert_called_once()
        factory.return_value.close.assert_called_once()
