"""Run the real client in an isolated headless browser with a captured fetch."""

import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from mycount.interface.VisitPayload import VisitPayload


ROOT = Path(__file__).resolve().parents[1]
CHROME = shutil.which('google-chrome') or shutil.which('chromium')


@unittest.skipUnless(CHROME, 'Chrome or Chromium is required for client execution tests')
class ClientTests(unittest.TestCase):
    def run_client(self, setup='', endpoint='https://count.osoyalce.com/count'):
        with tempfile.TemporaryDirectory(prefix='mycount-client-test-') as temporary:
            root = Path(temporary)
            page = root / 'test.html'
            page.write_text('''<!doctype html><pre id="result">null</pre><script>
                window.fetch = (url, options) => {
                    document.getElementById('result').textContent = JSON.stringify({url, options});
                    return Promise.resolve({ok: true, status: 204});
                };
            ''' + setup + '</script><script data-site="r3el" data-endpoint="'
                + html.escape(endpoint, quote=True) + '">'
                + (ROOT / 'client/mycount.js').read_text() + '</script>')
            result = subprocess.run([
                CHROME, '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                '--disable-background-networking', '--no-first-run', '--no-default-browser-check',
                f'--user-data-dir={root / "profile"}', '--dump-dom', page.as_uri(),
            ], capture_output=True, text=True, check=True, timeout=30)
            match = re.search(r'<pre id="result">(.*?)</pre>', result.stdout, re.DOTALL)
            self.assertIsNotNone(match, result.stderr)
            return json.loads(html.unescape(match.group(1)))

    def test_referrer_is_reduced_and_browser_payload_passes_validation(self):
        captured = self.run_client('''
            Object.defineProperty(document, 'referrer', {value: 'https://search.example/find?q=private#secret'});
        ''')
        self.assertEqual(captured['url'], 'https://count.osoyalce.com/count')
        self.assertEqual(captured['options']['credentials'], 'omit')
        self.assertEqual(captured['options']['referrerPolicy'], 'no-referrer')
        payload = json.loads(captured['options']['body'])
        self.assertEqual(payload['referrer'], 'https://search.example')
        self.assertNotIn('private', captured['options']['body'])
        self.assertIsInstance(payload['client_details']['viewport_width'], int)
        self.assertIsInstance(payload['client_details']['timezone'], str)
        # The test page is a local file, so substitute only its origin/path.
        payload['url'] = 'https://r3el.osoyalce.com/'
        visit, _ = VisitPayload().resolve(payload, 'https://r3el.osoyalce.com')
        self.assertEqual(visit.referrer_host, 'search.example')
        self.assertIsInstance(dict(visit.client_details)['webdriver'], bool)

    def test_missing_browser_apis_still_send_a_valid_visit(self):
        captured = self.run_client('''
            for (const key of ['connection', 'deviceMemory', 'globalPrivacyControl', 'pdfViewerEnabled']) {
                Object.defineProperty(navigator, key, {value: undefined});
            }
            window.matchMedia = undefined;
            Object.defineProperty(document, 'referrer', {value: ''});
        ''')
        payload = json.loads(captured['options']['body'])
        self.assertIsNone(payload['referrer'])
        self.assertNotIn('device_memory', payload['client_details'])
        self.assertNotIn('connection_rtt', payload['client_details'])
        self.assertIsNone(payload['client_details']['color_scheme'])
        payload['url'] = 'https://r3el.osoyalce.com/'
        visit, _ = VisitPayload().resolve(payload, 'https://r3el.osoyalce.com')
        self.assertNotIn('color_scheme', dict(visit.client_details))

    def test_empty_endpoint_disables_collection(self):
        self.assertIsNone(self.run_client(endpoint=''))
