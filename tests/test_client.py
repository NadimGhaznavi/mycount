"""Run the real client in an isolated headless browser with a captured fetch."""

import html
from contextlib import nullcontext
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from uuid import UUID

from mycount.interface.VisitPayload import VisitPayload


ROOT = Path(__file__).resolve().parents[1]
CHROME = shutil.which('google-chrome') or shutil.which('chromium')


@unittest.skipUnless(CHROME, 'Chrome or Chromium is required for client execution tests')
class ClientTests(unittest.TestCase):
    def run_client(self, setup='', endpoint='https://count.osoyalce.com/count', root=None, site='r3el'):
        context = nullcontext(root) if root is not None else tempfile.TemporaryDirectory(prefix='mycount-client-test-')
        with context as temporary:
            root = Path(temporary)
            page = root / 'test.html'
            page.write_text('''<!doctype html><pre id="result">null</pre><script>
                window.fetch = (url, options) => {
                    document.getElementById('result').textContent = JSON.stringify({url, options});
                    return Promise.resolve({ok: true, status: 204});
                };
            ''' + setup + '</script><script data-site="' + html.escape(site, quote=True) + '" data-endpoint="'
                + html.escape(endpoint, quote=True) + '">'
                + (ROOT / 'client/mycount.js').read_text() + '</script>')
            result = subprocess.run([
                CHROME, '--headless', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                '--disable-background-networking', '--virtual-time-budget=1000', '--no-first-run', '--no-default-browser-check',
                f'--user-data-dir={root / "profile"}', '--dump-dom', page.as_uri() + '?q=a%20b&q=two#section',
            ], capture_output=True, text=True, check=True, timeout=30)
            match = re.search(r'<pre id="result">(.*?)</pre>', result.stdout, re.DOTALL)
            self.assertIsNotNone(match, result.stderr)
            return json.loads(html.unescape(match.group(1)))

    def test_full_referrer_and_query_pass_payload_validation(self):
        captured = self.run_client('''
            Object.defineProperty(document, 'referrer', {value: 'https://search.example/find?q=private#secret'});
        ''')
        self.assertEqual(captured['url'], 'https://count.osoyalce.com/count')
        self.assertEqual(captured['options']['credentials'], 'omit')
        self.assertEqual(captured['options']['referrerPolicy'], 'no-referrer')
        payload = json.loads(captured['options']['body'])
        self.assertEqual(payload['referrer'], 'https://search.example/find?q=private#secret')
        self.assertEqual(payload['search'], '?q=a%20b&q=two')
        self.assertIsInstance(payload['client_details']['viewport_width'], int)
        self.assertIsInstance(payload['client_details']['timezone'], str)
        # The test page is a local file, so substitute only its origin/path.
        payload['url'] = 'https://r3el.osoyalce.com/'
        visit, _ = VisitPayload().resolve(payload, 'https://r3el.osoyalce.com')
        self.assertEqual(visit.referrer_host, 'search.example')
        self.assertEqual(visit.referrer, payload['referrer'])
        self.assertEqual(visit.search, payload['search'])
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

    def test_browser_id_persists_across_browser_restarts_and_separates_site_labels(self):
        with tempfile.TemporaryDirectory(prefix='mycount-identity-test-') as root:
            first = json.loads(self.run_client(root=root)['options']['body'])['visitor_id']
            second = json.loads(self.run_client(root=root)['options']['body'])['visitor_id']
            other = json.loads(self.run_client(root=root, site='ax3l')['options']['body'])['visitor_id']
            self.assertEqual(UUID(first).version, 4)
            self.assertEqual(first, second)
            self.assertNotEqual(first, other)

    def test_blocked_storage_keeps_collecting_without_a_visitor_id(self):
        for setup in (
            "Object.defineProperty(window, 'localStorage', {get() { throw new DOMException('blocked', 'SecurityError'); }});",
            "Storage.prototype.setItem = () => { throw new DOMException('full', 'QuotaExceededError'); };",
            "Storage.prototype.setItem = () => {};",
            "Object.defineProperty(window.crypto, 'randomUUID', {value: undefined});",
        ):
            with self.subTest(setup=setup):
                payload = json.loads(self.run_client(setup)['options']['body'])
                self.assertIsNone(payload['visitor_id'])

    def test_invalid_stored_id_is_replaced(self):
        for value in ('corrupt', '3e8073e0-5f15-4f14-bccc-b4b5cb47e330\n'):
            with self.subTest(value=value):
                setup = "localStorage.setItem('mycount.visitor_id.r3el', " + json.dumps(value) + ");"
                payload = json.loads(self.run_client(setup)['options']['body'])
                self.assertEqual(UUID(payload['visitor_id']).version, 4)
                self.assertEqual(len(payload['visitor_id']), 36)

    def test_counters_share_one_read_after_one_post(self):
        for failure in ('none', 'post', 'get', 'invalid'):
            with self.subTest(failure=failure):
                captured = self.run_client("const failure = " + json.dumps(failure) + ";" + r"""
                    document.write('<span data-mycount-counter>…</span><span data-mycount-counter>…</span>');
                    const calls = [];
                    let postFinished = false;
                    window.fetch = (url, options) => {
                        calls.push({url, method: options.method, postFinished});
                        if (options.method === 'POST') {
                            return new Promise((resolve, reject) => setTimeout(() => {
                                postFinished = true;
                                if (failure === 'post') reject(new Error('network'));
                                else resolve({ok: true, status: 204});
                            }, 10));
                        }
                        return Promise.resolve({ok: failure !== 'get',
                            json: () => Promise.resolve({site: 'r3el', visits: failure === 'invalid' ? -1 : 1234})});
                    };
                    let attempts = 0;
                    function capture() {
                        const labels = Array.from(document.querySelectorAll('[data-mycount-counter]'), node => node.textContent);
                        if (labels.some(label => label === '…') && ++attempts < 50) {
                            setTimeout(capture, 10);
                            return;
                        }
                        document.getElementById('result').textContent = JSON.stringify({calls,
                            labels,
                            expected: (1234).toLocaleString()});
                    }
                    setTimeout(capture, 10);
                """)
                self.assertEqual([call['method'] for call in captured['calls']], ['POST', 'GET'])
                self.assertTrue(captured['calls'][1]['postFinished'])
                self.assertEqual(captured['calls'][1]['url'], 'https://count.osoyalce.com/get_count?site=r3el')
                expected = '—' if failure in ('get', 'invalid') else captured['expected']
                self.assertEqual(captured['labels'], [expected, expected])
