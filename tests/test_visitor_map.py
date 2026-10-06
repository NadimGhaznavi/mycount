"""Verify visitor map filters, snapshot ownership, and safe location rendering."""

from datetime import date, datetime
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
import unittest
from unittest.mock import patch

import pymysql

from mycount.activity.ReadReports import ReadReports
from mycount.entity.Report import Report
from mycount.entity.ReportOptions import ReportOptions
from mycount.server.ControlHandler import ControlHandler
from mycount.server.ControlPages import ControlPages


class VisitorMapTests(unittest.TestCase):
    def setUp(self):
        self.options = ReportOptions(date(2026, 3, 8), date(2026, 3, 8), 'America/Toronto')
        self.locations = [
            dict(latitude=0.0, longitude=0.0, country_code=None, country_name=None,
                 region_name=None, city_name='<script>alert(1)</script>', page_views=4),
            dict(latitude=43.65, longitude=-79.38, country_code='CA', country_name='Canada',
                 region_name='Ontario', city_name='Toronto', page_views=2),
            dict(latitude=None, longitude=10.0, country_code=None, country_name=None,
                 region_name=None, city_name=None, page_views=3),
            dict(latitude=10.0, longitude=None, country_code=None, country_name=None,
                 region_name=None, city_name=None, page_views=1),
        ]

    @patch('mycount.activity.ReadReports.DbMgr')
    def test_map_reads_aggregates_in_snapshot_with_local_day_and_bot_filters(self, factory):
        first = datetime(2025, 1, 1)
        factory.return_value.query.side_effect = [self.locations, [dict(first_visit_at=first)]]
        report = ReadReports().visitor_map(self.options)
        self.assertEqual(report.locations, self.locations)
        self.assertEqual(report.first_visit_at, first)
        self.assertEqual(report.daily, [])
        factory.return_value.transaction.assert_called_once_with(read_only=True)
        factory.return_value.close.assert_called_once()
        sql, parameters = factory.return_value.query.call_args_list[0].args
        self.assertIn('GROUP BY latitude, longitude', sql)
        self.assertIn('COUNT(*) AS page_views', sql)
        self.assertIn('COALESCE(v.is_bot, 0) = 0', sql)
        self.assertEqual(parameters[-2:], (datetime(2026, 3, 8, 5), datetime(2026, 3, 9, 4)))
        self.assertNotIn('latitude IS NOT NULL', sql)
        self.assertEqual(factory.return_value.query.call_count, 2)

    def test_map_preserves_zero_coordinates_and_counts_missing_locations(self):
        mapped = [{**row, 'coordinate_source': 'GeoIP'} for row in self.locations[:2]]
        body = ControlPages().visitor_map(Report(self.options, [], None, locations=self.locations, map_locations=mapped)).decode()
        self.assertIn('6 mapped visits · 4 unmapped visits · 10 total visits', body)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', body)
        self.assertNotIn('<script>alert(1)</script>', body)
        markers = body.split('const locations = ', 1)[1].split(';', 1)[0]
        self.assertIn('"latitude": 0.0', markers)
        self.assertNotIn('"latitude": null', markers)
        self.assertNotIn('"longitude": null', markers)
        self.assertIn('popup.textContent =', body)
        self.assertIn('OpenStreetMap</a> contributors', body)
        self.assertIn('value="America/Toronto"', body)
        self.assertIn('value="1" checked', body)
        self.assertIn('<a href="/">Visitor Map</a>', ControlPages().reference().decode())
        self.assertNotIn('<a href="/">Visitor Map</a>', body)
        self.assertIn('<a href="/metrics">Metrics</a>', body)
        empty = ControlPages().visitor_map(Report(self.options, [], None)).decode()
        self.assertIn('No visits match the current filters.', empty)
        self.assertIn('0 mapped visits · 0 unmapped visits · 0 total visits', empty)
        missing = ControlPages().visitor_map(Report(self.options, [], None, locations=self.locations[2:])).decode()
        self.assertIn('No locations could be mapped', missing)

    @patch('mycount.activity.ReadReports.CityLocations')
    @patch('mycount.activity.ReadReports.DbMgr')
    def test_report_resolves_missing_city_after_database_snapshot_closes(self, factory, cities):
        missing = {**self.locations[1], 'latitude': None, 'longitude': None}
        factory.return_value.query.side_effect = [[missing], [dict(first_visit_at=None)]]
        def locate(rows):
            factory.return_value.close.assert_called_once()
            self.assertEqual(rows, [missing])
            return [(43.7, -79.4)]
        cities.return_value.locate.side_effect = locate
        report = ReadReports().visitor_map(self.options)
        self.assertIsNone(report.locations[0]['latitude'])
        self.assertEqual(report.map_locations[0]['latitude'], 43.7)
        self.assertEqual(report.map_locations[0]['coordinate_source'], 'CityDB')
        body = ControlPages().visitor_map(report).decode()
        self.assertIn('2 mapped visits · 0 unmapped visits · 2 total visits', body)
        self.assertIn('CityDB', body)


    @patch('mycount.activity.ReadReports.DbMgr')
    def test_http_filters_validation_and_database_failure(self, factory):
        for path in ('/', '/map'):
            with self.subTest(path=path):
                factory.reset_mock()
                factory.return_value.query.side_effect = [self.locations, [dict(first_visit_at=None)]]
                with ThreadingHTTPServer(('127.0.0.1', 0), ControlHandler) as server:
                    thread = Thread(target=server.serve_forever)
                    thread.start()
                    connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                    try:
                        connection.request('GET', path + '?start=2026-03-08&end=2026-03-08&timezone=America%2FToronto&exclude_bots=0')
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertIn(b'<h1>Visitor Map</h1>', response.read())
                        self.assertNotIn('COALESCE(v.is_bot, 0) = 0', factory.return_value.query.call_args_list[0].args[0])
                        factory.return_value.close.assert_called_once()
                        factory.reset_mock()
                        connection.request('GET', path + '?start=bad')
                        response = connection.getresponse()
                        self.assertEqual(response.status, 400)
                        response.read()
                        factory.assert_not_called()
                        factory.return_value.query.side_effect = pymysql.OperationalError('private details')
                        with self.assertLogs(level='ERROR'):
                            connection.request('GET', path)
                            response = connection.getresponse()
                            self.assertEqual(response.status, 503)
                            body = response.read()
                        self.assertIn(b'Visitor locations unavailable.', body)
                        self.assertNotIn(b'private details', body)
                        self.assertNotIn(b'L.map(', body)
                        factory.return_value.close.assert_called_once()
                        factory.return_value.transaction.return_value.__exit__.assert_called_once()
                    finally:
                        connection.close()
                        server.shutdown()
                        thread.join()
