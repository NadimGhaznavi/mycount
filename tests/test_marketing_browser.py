"""Execute marketing scripts around local midnight and daylight-saving transitions."""

import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from mycount.server.ControlPages import ControlPages


CHROME = shutil.which('google-chrome') or shutil.which('chromium')
TEMPLATES = Path(__file__).resolve().parents[1] / 'mycount/server/templates'


@unittest.skipUnless(CHROME, 'Chrome is required for marketing script checks')
class MarketingBrowserTests(unittest.TestCase):
    def test_posting_offsets_and_daily_totals_in_browser_timezone(self):
        pages = ControlPages()
        chart = pages._templates.get_template('marketing_chart.html').render(
            traffic_times=['2026-03-08T04:30:00+00:00', '2026-03-08T07:30:00+00:00',
                           '2026-03-10T04:30:00+00:00'],
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
