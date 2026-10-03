"""Execute marketing scripts around local midnight and daylight-saving transitions."""

import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.parse import parse_qs, urlsplit

from mycount.server.ControlPages import ControlPages
from mycount.interface.ReportQuery import ReportQuery


CHROME = shutil.which('google-chrome') or shutil.which('chromium')
TEMPLATES = Path(__file__).resolve().parents[1] / 'mycount/server/templates'


@unittest.skipUnless(CHROME, 'Chrome is required for marketing script checks')
class MarketingBrowserTests(unittest.TestCase):
    def test_report_filters_use_local_timezone_for_links_and_submissions(self):
        template = ControlPages()._templates.get_template('report_filters.html')
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                query = parse_qs(urlsplit(self.path).query)
                requests.append(query)
                options = ReportQuery.resolve(query)
                filters = template.render(options=options, exclude_bots=options.exclude_bots,
                                          error=query.get('error'))
                body = ('<!doctype html><pre id="result"></pre>' + filters + '''
                    <script>
                      document.getElementById('result').textContent = JSON.stringify({
                        fields: Object.fromEntries(new FormData(document.querySelector('form'))),
                        visibleTimezone: !!document.querySelector('input[name="timezone"]:not([type="hidden"])'),
                      });
                    </script>
                ''').encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for suffix, expected_requests in [('', 2), ('&timezone=Asia%2FTokyo', 2),
                                                   ('&timezone=America%2FToronto', 1),
                                                   ('&timezone=UTC&error=save', 1)]:
                    with self.subTest(suffix=suffix), TemporaryDirectory(prefix='mycount-filters-browser-') as temporary:
                        requests.clear()
                        result = subprocess.run([
                            CHROME, '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                            '--disable-background-networking', '--no-first-run', '--no-default-browser-check',
                            f'--user-data-dir={temporary}/profile', '--dump-dom',
                            f'http://127.0.0.1:{server.server_port}/?start=2026-03-07&end=2026-03-10&exclude_bots=0{suffix}',
                        ], env={**os.environ, 'TZ': 'America/Toronto'}, check=True,
                           capture_output=True, text=True, timeout=30)
                        match = re.search(r'<pre id="result">(.*?)</pre>', result.stdout, re.DOTALL)
                        self.assertIsNotNone(match, result.stderr)
                        captured = json.loads(html.unescape(match[1]))
                        self.assertFalse(captured['visibleTimezone'])
                        self.assertEqual(captured['fields'], dict(start='2026-03-07', end='2026-03-10',
                                                                 timezone='America/Toronto', exclude_bots='0'))
                        reports = [query for query in requests if 'start' in query]
                        self.assertEqual(len(reports), expected_requests)
                        if expected_requests == 2:
                            self.assertEqual(reports[-1]['timezone'], ['America/Toronto'])
            finally:
                server.shutdown()
                thread.join()

    def test_posting_offsets_and_daily_totals_in_browser_timezone(self):
        pages = ControlPages()
        chart = pages._templates.get_template('marketing_chart.html').render(
            daily=[{"day": day, "page_views": count} for day, count in
                   [('2026-03-07', 1), ('2026-03-08', 1), ('2026-03-09', 0), ('2026-03-10', 1)]],
            options=ReportQuery.resolve({'start': ['2026-03-07'], 'end': ['2026-03-10'], 'timezone': ['Asia/Tokyo']}),
            posting_times=[{'id': 1, 'platform': 'Reddit', 'posted_at': '2026-03-08T07:30:00+00:00'}])
        setup = '''
            const NativeDate = Date;
            window.Date = class extends NativeDate {
              constructor(...args) { super(...(args.length ? args : ['2026-03-10T12:00:00Z'])); }
            };
            const chartTheme = {colors: ['red', 'yellow'], layout: {}};
            let captured;
            const Plotly = {newPlot: (id, data, layout) => {
              captured = {data, layout};
              return Promise.resolve({on() {}});
            }};
        '''
        exercise = '''
            const input = document.getElementById('posted-at');
            const form = document.getElementById('marketing-form');
            const cases = [];
            for (const value of ['2026-01-15 12:00', '2026-07-15 12:00', '2026-03-08 02:30']) {
              input.value = value;
              input.dispatchEvent(new Event('input'));
              const event = new Event('submit', {cancelable: true});
              form.dispatchEvent(event);
              cases.push({value, rejected: event.defaultPrevented,
                          offset: document.getElementById('timezone-offset').value});
            }
            document.getElementById('result').textContent = JSON.stringify({cases, captured});
        '''
        with TemporaryDirectory(prefix='mycount-marketing-browser-') as temporary:
            root = Path(temporary)
            page = root / 'test.html'
            page.write_text('<!doctype html><pre id="result"></pre>'
                            '<form id="marketing-form"><input id="posted-at"><input id="timezone-offset"></form>'
                            '<script>' + setup + '</script>'
                            + (TEMPLATES / 'marketing_form.html').read_text() + chart
                            + '<script>' + exercise + '</script>')
            result = subprocess.run([
                CHROME, '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                '--disable-background-networking', '--no-first-run', '--no-default-browser-check',
                f'--user-data-dir={root / "profile"}', '--dump-dom', page.as_uri(),
            ], env={**os.environ, 'TZ': 'America/Toronto'}, check=True,
               capture_output=True, text=True, timeout=30)
            match = re.search(r'<pre id="result">(.*?)</pre>', result.stdout, re.DOTALL)
            self.assertIsNotNone(match, result.stderr)
            captured = json.loads(html.unescape(match[1]))
        self.assertEqual([case['rejected'] for case in captured['cases']], [False, False, True])
        self.assertEqual([case['offset'] for case in captured['cases'][:2]], ['300', '240'])
        visits, posts = captured['captured']['data']
        self.assertEqual(visits['x'], ['2026-03-07', '2026-03-08', '2026-03-09', '2026-03-10'])
        self.assertEqual(visits['y'], [1, 1, 0, 1])
        self.assertEqual(posts['x'], ['2026-03-08 03:30:00'])
        self.assertEqual(visits['line']['shape'], 'spline')
        self.assertEqual(visits['line']['smoothing'], 1)
