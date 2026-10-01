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
    def test_all_traffic_uses_all_matching_visits_and_follows_the_tables(self):
        recent = [
            {"received_at": datetime(2026, 9, 27, 3, 30), "country_code": None,
             "city_name": None, "url": "https://one.example/"},
            {"received_at": datetime(2026, 9, 27, 4, 30), "country_code": None,
             "city_name": None, "url": "https://two.example/"},
        ]
        body = ControlPages().render([], [], [], recent, []).decode()
        self.assertGreater(body.index('<section class="traffic-chart"'), body.rindex('</table>'))
        self.assertIn('>All Traffic</h2>', body)
        self.assertIn('const timestamps = ["2026-09-27T03:30:00+00:00", "2026-09-27T04:30:00+00:00"]', body)
        self.assertIn("Plotly.newPlot('all-traffic'", body)
        empty = ControlPages().render([], [], [], [], []).decode()
        chart = empty.split('<section class="traffic-chart"', 1)[1].split('</section>', 1)[0]
        self.assertIn('No visits match the current filters.', chart)
        self.assertNotIn('cdn.plot.ly', empty)

    def test_counting_since_uses_first_visit_date_and_hides_when_unknown(self):
        pages = ControlPages()
        first = datetime(2025, 2, 3, 1, 30)
        for body in (pages.render([], [], [], [], [], first_visit_at=first), pages.reference(first)):
            self.assertIn(b'Counting since <time datetime="2025-02-03T01:30:00+00:00" data-local-time="long-date">February 3, 2025</time>', body)
            self.assertNotIn(b'September XX', body)
        for body in (pages.render([], [], [], [], []), pages.reference()):
            self.assertNotIn(b'Counting since', body)

    def test_country_pie_combines_cities_and_preserves_unknown_visits(self):
        locations = [
            {"country_name": "Canada", "country_code": "CA", "region_name": "Ontario", "city_name": "Toronto", "page_views": 2},
            {"country_name": "Canada", "country_code": "CA", "region_name": "Quebec", "city_name": "Montreal", "page_views": 4},
            {"country_name": "<Country>", "country_code": "US", "region_name": None, "city_name": None, "page_views": 3},
            {"country_name": None, "country_code": None, "region_name": None, "city_name": None, "page_views": 1},
        ]
        body = ControlPages().render([], [], locations, [], []).decode()
        chart = body.split('<section class="country-chart"', 1)[1].split('</section>', 1)[0]
        self.assertIn('>Visits by Location</h2>', chart)
        self.assertIn('>Canada</span><span class="country-value">6 (60.0%)', chart)
        self.assertIn('>&lt;Country&gt;</span><span class="country-value">3 (30.0%)', chart)
        self.assertIn('>Unknown</span><span class="country-value">1 (10.0%)', chart)
        self.assertIn("drawPie('country-pie'", body)
        self.assertIn('[6, 3, 1]', body)
        self.assertNotIn('Toronto', chart)
        single = ControlPages().render([], [], locations[:1], [], [])
        self.assertIn(b"drawPie('country-pie'", single)
        self.assertIn(b'2 (100.0%)', single)
        empty = ControlPages().render([], [], [], [], []).decode().split('<section class="country-chart"', 1)[1]
        self.assertIn('No visits match the current filters.', empty)
        self.assertNotIn('conic-gradient(', empty)

    def test_site_pie_uses_site_totals_and_escapes_legend_names(self):
        sites = [
            {"site": "<one>", "page_views": 3, "last_visited": datetime(2026, 9, 27)},
            {"site": "two.example", "page_views": 1, "last_visited": datetime(2026, 9, 27)},
        ]
        pages = [{**site, "url": f'https://{site["site"]}/'} for site in sites]
        body = ControlPages().render(sites, pages, [], [], []).decode()
        chart = body.split('<section class="site-chart"', 1)[1].split('</section>', 1)[0]
        self.assertIn('>Visits by Site</h2>', chart)
        self.assertIn('&lt;one&gt;</span><span class="country-value">3 (75.0%)', chart)
        self.assertIn('two.example</span><span class="country-value">1 (25.0%)', chart)
        self.assertIn("drawPie('site-pie'", body)
        self.assertIn('[3, 1]', body)
        self.assertEqual(body.count('src="https://cdn.plot.ly/'), 1)

    @patch("mycount.server.ControlHandler.DbMgr")
    def test_banner_health_and_missing_page(self, factory):
        factory.return_value.query.side_effect = [
            [{"site": "<example>", "page_views": 12, "last_visited": datetime(2026, 9, 27, 15, 5)}],
            [{"site": "<example>", "url": "https://example.com/<page>", "page_views": 12,
              "last_visited": datetime(2026, 9, 27, 15, 5)}],
            [{"country_name": "Canada", "country_code": "CA", "region_name": "Ontario", "city_name": "<city>", "page_views": 9},
             {"country_name": None, "country_code": "", "region_name": None, "city_name": None, "page_views": 3}],
            [{"received_at": datetime(2026, 9, 27, 15, 5), "country_code": "CA", "city_name": "Hamilton", "url": "https://example.com/<recent>"}],
            [{"referrer_host": "<referrer>", "page_views": 8},
             {"referrer_host": None, "page_views": 4}],
            [{"first_visit_at": datetime(2026, 9, 23, 12)}],
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
                    self.assertIn(b'data-local-time="long-date">September 23, 2026</time>', body)
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
                    referrers = body.split(b'<table aria-label="Referrers">', 1)[1].split(b'</table>', 1)[0]
                    self.assertIn(b'<caption>Referrers</caption>', referrers)
                    self.assertIn(b'<td>&lt;referrer&gt;</td><td class="visits">8</td>', referrers)
                    self.assertIn(b'<td>Direct / Unknown</td><td class="visits">4</td>', referrers)
                    self.assertIn(b'<tfoot><tr><th scope="row">Total:</th><td class="visits">12</td>', referrers)
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
                    for call in factory.return_value.query.call_args_list[:-1]:
                        self.assertIn('COALESCE(v.is_bot, 0) = 0', call.args[0])
                    self.assertNotIn('WHERE', factory.return_value.query.call_args_list[-1].args[0])
                    for query, excluded in [('exclude_bots=0', False), ('exclude_bots=0&exclude_bots=1', True)]:
                        factory.reset_mock()
                        factory.return_value.query.side_effect = [[], [], [], [], [], [{"first_visit_at": datetime(2026, 9, 23, 12)}]]
                        connection.request("GET", "/?" + query)
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        filtered = response.read()
                        self.assertEqual(b'value="1" checked' in filtered, excluded)
                        self.assertEqual(filtered.count(b'class="visits">0</td>'), 3)
                        self.assertIn(b'<caption>Referrers</caption>', filtered)
                        self.assertIn(b'data-local-time="long-date">September 23, 2026</time>', filtered)
                        for call in factory.return_value.query.call_args_list[:-1]:
                            self.assertEqual('COALESCE(v.is_bot, 0) = 0' in call.args[0], excluded)
                    factory.reset_mock()
                    factory.return_value.query.side_effect = [[{"first_visit_at": datetime(2026, 9, 23, 12)}]]
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
                    self.assertIn(b'data-local-time="long-date">September 23, 2026</time>', reference)
                    factory.return_value.close.assert_called_once()
                    factory.reset_mock()
                    connection.request("GET", "/health")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read()), {"status": "ok", "service": "mycount-control"})
                    factory.assert_not_called()
                    factory.return_value.query.side_effect = pymysql.OperationalError("private details")
                    with self.assertLogs(level="ERROR"):
                        connection.request("GET", "/reference")
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        reference = response.read()
                    self.assertIn(b'Optional browser details', reference)
                    self.assertNotIn(b'Counting since', reference)
                    self.assertNotIn(b'private details', reference)
                    factory.return_value.close.assert_called_once()
                    factory.reset_mock()
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
                 "assert b'MyCount <span>Control</span>' in ControlPages().render([], [], [], [], []); "
                 "assert b'Optional browser details' in ControlPages().reference()"],
                cwd=directory, check=True,
            )
