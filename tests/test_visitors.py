"""Visitor table rendering, filters, pagination, and HTTP error handling."""

from datetime import datetime
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import unittest

import pymysql

from mycount.activity.ReadReports import ReadReports
from mycount.constants.DVisitors import DVisitors
from mycount.entity.Report import Report
from mycount.interface.ReportQuery import ReportQuery
from mycount.interface.VisitorsQuery import VisitorsQuery
from mycount.server.ControlHandler import ControlHandler
from mycount.server.ControlPages import ControlPages


class VisitorsTests(unittest.TestCase):
    def test_table_has_filter_row_and_escapes_records_and_filters(self):
        row = dict.fromkeys(name for name, _ in DVisitors.COLUMNS)
        row.update(received_at=datetime(2026, 10, 9, 12), site='<script>bad</script>',
                   url='https://example.com/', is_bot=0, visitor_id='AB' * 16)
        report = Report(ReportQuery.resolve({}), [], None, recent=[row],
                        older=(row['received_at'], 10))
        filters = {'site': '<script>bad</script>'}
        body = ControlPages().visitors(report, filters).decode()
        self.assertEqual(body.count('<table '), 1)
        self.assertEqual(body.count('<input type="text"'), len(DVisitors.COLUMNS))
        headings, filter_row = body.split('<thead>')[1].split('</thead>')[0].split('</tr>')[:2]
        self.assertIn('Received at (UTC)', headings)
        self.assertIn('aria-label="Filter Site"', filter_row)
        self.assertIn('&lt;script&gt;bad&lt;/script&gt;', body)
        self.assertNotIn('<script>bad</script>', body)
        self.assertIn('2026-10-09 12:00:00', body)
        self.assertIn('<td>0</td>', body)
        self.assertIn('<td>—</td>', body)
        navigation = ControlPages().reference().decode()
        self.assertIn('href="/visitors"', navigation)
        navigation = ControlPages().marketing(Report(report.options, [], None)).decode()
        self.assertLess(navigation.index('href="/visitors"'), navigation.index('href="/reference"'))
        query = parse_qs(urlsplit(VisitorsQuery.link(filters, report.older)).query)
        self.assertEqual(VisitorsQuery.filters(query), filters)
        self.assertEqual(ReportQuery.resolve(query).before, report.older)
        with self.assertRaises(ValueError):
            VisitorsQuery.filters({'site': ['one', 'two']})

    @patch('mycount.activity.ReadReports.DbMgr')
    def test_snapshot_bounds_rows_and_closes_connection_on_failure(self, factory):
        timestamp = datetime(2026, 10, 9)
        factory.return_value.query.side_effect = [
            [dict(received_at=timestamp, page_view_id=index) for index in range(31, 0, -1)],
            [dict(first_visit_at=timestamp)],
        ]
        report = ReadReports().visitors(ReportQuery.resolve({}), {'site': 'example'})
        self.assertEqual(len(report.recent), 30)
        self.assertEqual(report.older, (timestamp, 2))
        factory.return_value.transaction.assert_called_once_with(read_only=True)
        factory.return_value.close.assert_called_once()
        factory.reset_mock()
        factory.return_value.query.side_effect = pymysql.OperationalError('offline')
        with self.assertRaises(pymysql.OperationalError):
            ReadReports().visitors(ReportQuery.resolve({}), {})
        factory.return_value.close.assert_called_once()
        factory.return_value.transaction.return_value.__exit__.assert_called_once()

    @patch('mycount.activity.ReadReports.DbMgr')
    def test_http_filters_validation_empty_and_database_error(self, factory):
        server = ThreadingHTTPServer(('127.0.0.1', 0), ControlHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = HTTPConnection(*server.server_address, timeout=5)
        try:
            factory.return_value.query.side_effect = [[], [dict(first_visit_at=None)]]
            connection.request('GET', '/visitors?site=50%25_%3D&is_bot=0')
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn(b'No visits match the current filters.', response.read())
            parameters = factory.return_value.query.call_args_list[0].args[1]
            self.assertEqual(parameters, ('%50=%=_==%', '%0%', 31))
            for path in ('/visitors?before=bad', '/visitors?site=one&site=two'):
                connection.request('GET', path)
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
                response.read()
            factory.return_value.query.side_effect = pymysql.OperationalError('private details')
            with self.assertLogs(level='ERROR'):
                connection.request('GET', '/visitors?site=example')
                response = connection.getresponse()
                self.assertEqual(response.status, 503)
                body = response.read()
            self.assertIn(b'Visitor records unavailable.', body)
            self.assertIn(b'value="example"', body)
            self.assertNotIn(b'private details', body)
        finally:
            connection.close()
            server.shutdown()
            server.server_close()
            thread.join()
