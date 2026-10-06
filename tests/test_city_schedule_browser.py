"""Exercise schedule loading, saving, and failure feedback in Chrome."""

import html
import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from mycount.server.ControlPages import ControlPages


CHROME = shutil.which('google-chrome') or shutil.which('chromium')


@unittest.skipUnless(CHROME, 'Chrome is required for scheduling UI checks')
class CityScheduleBrowserTests(unittest.TestCase):
    def test_schedule_ui_loads_saves_disables_and_reports_errors(self):
        template = ControlPages()._templates.get_template('city_schedule.html').render()
        for mode in ('save', 'invalid', 'timeout', 'load-error'):
            with self.subTest(mode=mode), TemporaryDirectory(prefix='mycount-schedule-browser-') as directory:
                source = '''<!doctype html><meta charset="utf-8"><script>
                  const calls = [];
                  window.fetch = async (url, options) => {
                    calls.push({url, method: options.method || 'GET', body: options.body});
                    if (MODE === 'load-error') return {ok: false, json: async () => ({error: 'Schedule unavailable.'})};
                    if (options.method === 'POST' && MODE === 'timeout') throw new DOMException('timeout', 'TimeoutError');
                    if (options.method === 'POST' && MODE === 'invalid') return {ok: false, json: async () => ({error: 'Use five cron fields.'})};
                    return {ok: true, json: async () => ({schedule: options.body ? JSON.parse(options.body) : {enabled: true, expression: '0 3 1 */3 *'}, dataset: {available: true, city_count: 123, refreshed_at: '2026-10-06T12:00:00+00:00'}})};
                  };
                </script>''' .replace('MODE', json.dumps(mode)) + template + '''
                <pre id="result"></pre><script>
                  setTimeout(async () => {
                    const expression = document.getElementById('schedule-expression');
                    const enabled = document.getElementById('schedule-enabled');
                    const initial = {expression: expression.value, enabled: enabled.checked, disabled: expression.disabled};
                    if (!expression.disabled) {
                      expression.value = '0 4 * * 0'; enabled.checked = false;
                      document.getElementById('schedule-form').dispatchEvent(new Event('submit', {cancelable: true}));
                      await new Promise(resolve => setTimeout(resolve, 20));
                    }
                    document.getElementById('result').textContent = JSON.stringify({initial, calls, disabled: expression.disabled, status: document.getElementById('schedule-status').textContent, dataset: document.getElementById('city-data-status').textContent});
                  }, 50);
                </script>'''
                path = Path(directory) / 'page.html'
                path.write_text(source)
                result = subprocess.run([CHROME, '--headless', '--no-sandbox', '--disable-gpu',
                                         '--disable-dev-shm-usage', '--disable-background-networking',
                                         '--no-first-run', '--no-default-browser-check',
                                         f'--user-data-dir={directory}/profile', '--virtual-time-budget=1000',
                                         '--dump-dom', path.as_uri()], capture_output=True, text=True,
                                        check=True, timeout=30)
                match = re.search(r'<pre id="result">(.*?)</pre>', result.stdout, re.DOTALL)
                self.assertIsNotNone(match, result.stderr)
                captured = json.loads(html.unescape(match[1]))
                self.assertEqual(captured['calls'][0]['url'], '/api/city-schedule')
                if mode == 'load-error':
                    self.assertTrue(captured['disabled'])
                    self.assertIn('Schedule unavailable.', captured['status'])
                    self.assertEqual(len(captured['calls']), 1)
                else:
                    self.assertEqual(captured['initial'], dict(expression='0 3 1 */3 *', enabled=True, disabled=False))
                    self.assertFalse(captured['disabled'])
                    self.assertEqual(json.loads(captured['calls'][1]['body']), dict(enabled=False, expression='0 4 * * 0'))
                    self.assertIn('123 cities available', captured['dataset'])
                    if mode == 'save':
                        self.assertIn('Schedule saved. Scheduled city refresh disabled.', captured['status'])
                    elif mode == 'invalid':
                        self.assertIn('Use five cron fields.', captured['status'])
                    else:
                        self.assertIn('Reload to check the saved schedule', captured['status'])
