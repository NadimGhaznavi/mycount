"""Verify control HTTP responses and deployed presentation assets."""

from datetime import datetime
from unittest.mock import patch

import pymysql

from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from mycount.server.ControlHandler import ControlHandler
from mycount.server.ControlPages import ControlPages


class ControlServerTests(unittest.TestCase):
    def test_country_pie_combines_cities_and_preserves_unknown_visits(self):
        locations = [
            {"country_name": "Canada", "country_code": "CA", "region_name": "Ontario", "city_name": "Toronto", "page_views": 2},
            {"country_name": "Canada", "country_code": "CA", "region_name": "Quebec", "city_name": "Montreal", "page_views": 4},
            {"country_name": "<Country>", "country_code": "US", "region_name": None, "city_name": None, "page_views": 3},
            {"country_name": None, "country_code": None, "region_name": None, "city_name": None, "page_views": 1},
        ]
        body = ControlPages().render([], [], locations, []).decode()
        chart = body.split('<section class="country-chart"', 1)[1].split('</section>', 1)[0]
        self.assertIn('>Visits by Location</h2>', chart)
        self.assertIn('>Canada</span><span class="country-value">6 (60.0%)', chart)
        self.assertIn('>&lt;Country&gt;</span><span class="country-value">3 (30.0%)', chart)
        self.assertIn('>Unknown</span><span class="country-value">1 (10.0%)', chart)
        for interval in ('0.0% 60.0%', '60.0% 90.0%', '90.0% 100.0%'):
            self.assertIn(interval, chart)
        self.assertNotIn('Toronto', chart)
        single = ControlPages().render([], [], locations[:1], [])
        self.assertIn(b'0.0% 100.0%', single)
        self.assertIn(b'2 (100.0%)', single)
        empty = ControlPages().render([], [], [], []).decode().split('<section class="country-chart"', 1)[1]
        self.assertIn('No visits match the current filters.', empty)
        self.assertNotIn('conic-gradient(', empty)

    @patch("mycount.server.ControlHandler.DbMgr")
    def test_banner_health_and_missing_page(self, factory):
        factory.return_value.query.side_effect = [
            [{"site": "<example>", "page_views": 12, "last_visited": datetime(2026, 9, 27, 15, 5)}],
            [{"site": "<example>", "url": "https://example.com/<page>", "page_views": 12,
              "last_visited": datetime(2026, 9, 27, 15, 5)}],
            [{"country_name": "Canada", "country_code": "CA", "region_name": "Ontario", "city_name": "<city>", "page_views": 9},
             {"country_name": None, "country_code": "", "region_name": None, "city_name": None, "page_views": 3}],
            [{"received_at": datetime(2026, 9, 27, 15, 5), "country_code": "CA", "city_name": "Hamilton", "url": "https://example.com/<recent>"}],
        ]
        with ThreadingHTTPServer(("127.0.0.1", 0), ControlHandler) as server:
            thread = Thread(target=server.serve_forever)
            thread.start()
            try:
                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
                try:
                    connection.request("GET", "/")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.getheader("Content-Type"), "text/html; charset=utf-8")
                    body = response.read()
                    self.assertIn(b"MyCount <span>Control</span>", body)
                    self.assertIn(b"&lt;example&gt;", body)
                    self.assertIn(b">12</td>", body)
                    self.assertIn(b'2026-09-27T15:05:00+00:00', body)
                    self.assertIn(b"Last refresh:", body)
                    self.assertIn(b'https://example.com/&lt;page&gt;', body)
                    self.assertIn(b'aria-expanded="false"', body)
                    self.assertIn(b'aria-controls="site-pages-1"', body)
                    self.assertIn(b'class="site-pages" hidden', body)
                    self.assertIn(b'<caption>Recent Visits</caption>', body)
                    self.assertIn(b'https://example.com/&lt;recent&gt;', body)
                    self.assertIn(b'data-local-time="date-only"', body)
                    self.assertIn(b'data-local-time="time-12"', body)
                    self.assertIn(b'>Visits by Site</th>', body)
                    self.assertIn(b'<caption>Visits by Location</caption>', body)
                    self.assertIn(b'&lt;city&gt;', body)
                    self.assertIn(b'>State/Province</th>', body)
                    self.assertIn(b'<td>Ontario</td>', body)
                    self.assertIn('aria-label="Country: CA">🇨🇦</span> Canada</td>'.encode(), body)
                    self.assertNotIn(b'>Continent</th>', body)
                    self.assertEqual(body.count(b'<td>---</td>'), 2)
                    self.assertIn(b'<td data-sort-value="---">---</td>', body)
                    self.assertIn(b'>9</td>', body)
                    self.assertIn(b'>3</td>', body)
                    factory.return_value.transaction.assert_called_once_with(read_only=True)
                    factory.return_value.close.assert_called_once()
                    self.assertIn(b'value="1" checked', body)
                    for call in factory.return_value.query.call_args_list:
                        self.assertIn('COALESCE(v.is_bot, 0) = 0', call.args[0])
                    for query, excluded in [('exclude_bots=0', False), ('exclude_bots=0&exclude_bots=1', True)]:
                        factory.reset_mock()
                        factory.return_value.query.side_effect = [[], [], [], []]
                        connection.request("GET", "/?" + query)
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        filtered = response.read()
                        self.assertEqual(b'value="1" checked' in filtered, excluded)
                        self.assertEqual(filtered.count(b'class="visits">0</td>'), 2)
                        for call in factory.return_value.query.call_args_list:
                            self.assertEqual('COALESCE(v.is_bot, 0) = 0' in call.args[0], excluded)
                    factory.reset_mock()
                    connection.request("GET", "/reference")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    reference = response.read()
                    self.assertIn(b'<h1>Visitor Data</h1>', reference)
                    self.assertIn(b'Optional browser details', reference)
                    self.assertIn(b'<code>global_privacy_control</code>', reference)
                    self.assertEqual(reference.count(b'<table '), 1)
                    for heading in (b'Source', b'Source Details', b'Table', b'Column', b'Details'):
                        self.assertIn(b'<th scope="col">' + heading + b'</th>', reference)
                    self.assertIn(b'GeoIP CSV</td><td>accuracy</td><td>---</td><td>---</td>', reference)
                    self.assertIn(b'href="/reference" aria-current="page"', reference)
                    self.assertNotIn(b"document.querySelectorAll('table')", reference)
                    factory.assert_not_called()
                    connection.request("GET", "/health")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read()), {"status": "ok", "service": "mycount-control"})
                    factory.assert_not_called()
                    factory.return_value.query.side_effect = pymysql.OperationalError("private details")
                    with self.assertLogs(level="ERROR"):
                        connection.request("GET", "/")
                        response = connection.getresponse()
                        self.assertEqual(response.status, 503)
                        body = response.read()
                    self.assertIn(b"Site visits unavailable", body)
                    self.assertNotIn(b"private details", body)
                    factory.return_value.close.assert_called_once()
                    connection.request("GET", "/missing")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 404)
                    response.read()
                finally:
                    connection.close()
            finally:
                server.shutdown()
                thread.join()

    def test_installed_entry_point_and_templates(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            # Use the same package copy rule as installation, outside the checkout.
            shutil.copytree(root / "mycount", Path(directory) / "mycount",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            result = subprocess.run(
                [sys.executable, "-B", "-m", "mycount.server.ControlServer", "--help"],
                cwd=directory, capture_output=True, text=True, check=True,
            )
            self.assertIn("--port", result.stdout)
            subprocess.run(
                [sys.executable, "-B", "-c",
                 "from mycount.server.ControlPages import ControlPages; "
                 "assert b'MyCount <span>Control</span>' in ControlPages().render([], [], [], []); "
                 "assert b'Optional browser details' in ControlPages().reference()"],
                cwd=directory, check=True,
            )
