"""Exercise filter defaults and navigation with a browser's cookie behavior."""

from dataclasses import replace
from html import unescape
from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer
import re
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

from mycount.entity.Report import Report
from mycount.server.ControlHandler import ControlHandler


class ReportPreferencesTests(unittest.TestCase):
    def setUp(self):
        reports = patch('mycount.server.ControlHandler.ReadReports')
        self.reports = reports.start().return_value
        self.addCleanup(reports.stop)
        for name in ('metrics', 'visitor_map', 'marketing', 'visitors'):
            getattr(self.reports, name).side_effect = lambda options, *args, **kwargs: Report(options, [], None)
        self.reports.first_visit_at.return_value = None
        forest = patch('mycount.server.ControlHandler.ReadIsoForest')
        forest.start().return_value.read.return_value = dict(
            runs=[], selected=None, observations=[], first_visit_at=None)
        self.addCleanup(forest.stop)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), ControlHandler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
        self.cookies = CookieJar()
        self.browser = build_opener(HTTPCookieProcessor(self.cookies))

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get(self, path, *, browser=None):
        with (browser or self.browser).open(self.origin + path, timeout=5) as response:
            self.assertEqual(response.status, 200)
            return response.read().decode()

    def follow(self, body, label):
        link = re.search(r'<a href="([^"]+)">' + re.escape(label) + r'</a>', body)
        self.assertIsNotNone(link, label)
        return self.get(unescape(link[1]))

    def test_isoforest_default_across_reports_and_session_cookie(self):
        body = self.get('/')
        self.assertTrue(self.reports.visitor_map.call_args.kwargs['all_history'])
        for label, method in (('Metrics', 'metrics'), ('Marketing', 'marketing'), ('Visitors', 'visitors')):
            self.assertIn('value="isoforest_plus" selected>IsoForest+</option>', body)
            body = self.follow(body, label)
            self.assertEqual(getattr(self.reports, method).call_args.args[0].filter_mode, 'isoforest_plus')
        self.assertIn('value="isoforest_plus" selected>IsoForest+</option>', body)
        self.assertTrue(self.reports.metrics.call_args.kwargs['all_history'])
        cookie, = self.cookies
        self.assertTrue(cookie.discard)
        self.assertIsNone(cookie.expires)
        self.assertTrue(cookie.has_nonstandard_attr('HttpOnly'))
        self.assertNotIn('start=', cookie.value)

    def test_shared_settings_survive_navigation_and_explicit_choices_override(self):
        body = self.get('/metrics?site=blog&start=2026-11-06&end=2026-11-12'
                        '&timezone=Asia%2FShanghai&filter=basic&before=2026-11-10T12:00:00,99')
        original = self.reports.metrics.call_args.args[0]
        self.assertIsNotNone(original.before)
        expected = replace(original, before=None)
        body = self.follow(body, 'Map')
        self.assertEqual(self.reports.visitor_map.call_args.args[0], expected)
        self.assertFalse(self.reports.visitor_map.call_args.kwargs['all_history'])
        body = self.follow(body, 'Marketing')
        self.assertEqual(self.reports.marketing.call_args.args[0], expected)
        body = self.follow(body, 'Reference')
        body = self.follow(body, 'Visitors')
        self.assertEqual(self.reports.visitors.call_args.args, (expected, {}))
        body = self.get('/visitors?site=50%25_%3D&filter=none&before=2026-11-10T12:00:00,98')
        self.assertEqual(self.reports.visitors.call_args.args[1], {'site': '50%_='})
        body = self.follow(body, 'IsoForest')
        body = self.follow(body, 'Metrics')
        expected = replace(expected, filter_mode='none')
        self.assertEqual(self.reports.metrics.call_args.args[0], expected)
        self.assertIn('value="none" selected', body)

        self.get('/marketing?exclude_bots=0&exclude_bots=1&site=other')
        expected = replace(expected, filter_mode='basic', site='other')
        self.assertEqual(self.reports.marketing.call_args.args[0], expected)
        body = self.get('/metrics')
        self.assertEqual(self.reports.metrics.call_args.args[0], expected)
        self.assertIn('value="basic" selected', body)
        self.get('/metrics?filter=isoforest_plus&exclude_bots=0')
        body = self.get('/map')
        self.assertEqual(self.reports.visitor_map.call_args.args[0], replace(expected, filter_mode='isoforest_plus'))
        self.assertIn('value="isoforest_plus" selected', body)

        body = self.get('/', browser=build_opener(HTTPCookieProcessor(CookieJar())))
        fresh = self.reports.visitor_map.call_args.args[0]
        self.assertEqual(fresh.site, '*')
        self.assertEqual(fresh.filter_mode, 'isoforest_plus')
        self.assertTrue(self.reports.visitor_map.call_args.kwargs['all_history'])

    def test_invalid_remembered_settings_are_validated_before_reading_reports(self):
        for cookie in ('filter=invalid', 'timezone=Missing%2FZone', 'site=%3Cscript%3E',
                       'filter=none&filter=basic', 'start=2026-02-30'):
            with self.subTest(cookie=cookie), self.assertRaises(HTTPError) as raised:
                urlopen(Request(self.origin + '/metrics', headers={
                    'Cookie': f'mycount_report_filters="{cookie}"'}), timeout=5)
            self.assertEqual(raised.exception.code, 400)
            raised.exception.close()
        self.reports.metrics.assert_not_called()
