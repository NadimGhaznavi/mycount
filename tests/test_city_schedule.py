"""Exercise BMDynIP-style scheduling without changing system cron."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.message import Message
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from mycount.interface.CitySchedule import CitySchedule
from mycount.interface.CityLocations import CityLocations
from mycount.server.ControlHandler import ControlHandler


class CityScheduleTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.schedule = CitySchedule(self.root)

    def test_install_preserves_custom_and_disabled_schedules(self):
        self.assertEqual(self.schedule.install(), dict(enabled=True, expression='0 3 1 */3 *'))
        self.schedule.update(False, '30 4 * * 1-5')
        reloaded = CitySchedule(self.root)
        self.assertEqual(reloaded.install(), dict(enabled=False, expression='30 4 * * 1-5'))
        self.assertFalse(reloaded.due(datetime(2026, 10, 5, 4, 30)))

    def test_invalid_settings_and_write_failure_preserve_schedule(self):
        self.schedule.install()
        original = (self.root / 'schedule.json').read_bytes()
        for enabled, expression in ((1, '* * * * *'), (True, '@daily'), (True, '60 * * * *'),
                                    (True, '* * * * *\n'), (True, '* * * * * /command'), (True, None)):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                self.schedule.update(enabled, expression)
        with patch('pathlib.Path.replace', side_effect=OSError('denied')), self.assertRaises(OSError):
            self.schedule.update(False, '0 3 * * 0')
        self.assertEqual((self.root / 'schedule.json').read_bytes(), original)
        self.assertEqual(list(self.root.glob('.schedule-*')), [])

    def test_quarterly_weekday_names_ranges_and_cron_day_or_semantics(self):
        for month in range(1, 13):
            self.assertEqual(self.schedule.due(datetime(2026, month, 1, 3)), month in (1, 4, 7, 10))
        self.assertFalse(self.schedule.due(datetime(2026, 10, 1, 3, 1)))
        self.schedule.update(True, '*/15 3-5 * * MON-FRI')
        self.assertTrue(self.schedule.due(datetime(2026, 10, 5, 4, 30)))
        self.assertFalse(self.schedule.due(datetime(2026, 10, 4, 4, 30)))
        self.schedule.update(True, '0 3 1 * 7')
        self.assertTrue(self.schedule.due(datetime(2026, 10, 4, 3)))
        self.assertTrue(self.schedule.due(datetime(2026, 10, 1, 3)))
        self.assertFalse(self.schedule.due(datetime(2026, 10, 2, 3)))

    def test_concurrent_saves_leave_one_complete_schedule(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.schedule.update, enabled, expression)
                       for enabled, expression in ((True, '*/5 * * * *'), (False, '0 3 * * 0'))]
            for future in futures:
                future.result(timeout=5)
        self.assertIn(self.schedule.read(), [dict(enabled=True, expression='*/5 * * * *'),
                                            dict(enabled=False, expression='0 3 * * 0')])

    def request(self, method='GET', body=b'', headers=None):
        handler = object.__new__(ControlHandler)
        handler.path = '/api/city-schedule'
        handler.headers = Message()
        for key, value in {'Host': 'localhost', 'Content-Type': 'application/json',
                           'Content-Length': str(len(body)), **(headers or {})}.items():
            handler.headers[key] = value
        handler.rfile = BytesIO(body)
        handler.respond = Mock()
        handler.send_error = Mock()
        with patch('mycount.server.ControlHandler.CitySchedule', return_value=self.schedule, wraps=CitySchedule), \
                patch('mycount.server.ControlHandler.CityLocations', return_value=CityLocations(self.root)):
            getattr(handler, 'do_' + method)()
        if handler.send_error.called:
            return handler.send_error.call_args.args[0], {}
        status, response, mime = handler.respond.call_args.args
        self.assertIn('application/json', mime)
        return status, json.loads(response)

    def test_api_reads_updates_and_rejects_invalid_or_cross_origin_writes(self):
        status, payload = self.request()
        self.assertEqual(status, 200)
        self.assertFalse(payload['dataset']['available'])
        values = dict(enabled=False, expression='0 3 * * 0')
        status, payload = self.request('POST', json.dumps(values).encode())
        self.assertEqual((status, payload['schedule']), (200, values))
        self.assertEqual(self.request()[1]['schedule'], values)
        for body in (b'{', b'[]', b'{}', b'{"enabled":true,"expression":"@daily"}',
                     b'{"enabled":true,"expression":"* * * * *","extra":1}'):
            self.assertEqual(self.request('POST', body)[0], 400)
        for headers, status in (({'Origin': 'https://other.example'}, 403),
                                ({'Sec-Fetch-Site': 'cross-site'}, 403),
                                ({'Content-Type': 'text/plain'}, 415),
                                ({'Transfer-Encoding': 'chunked'}, 400)):
            self.assertEqual(self.request('POST', json.dumps(values).encode(), headers)[0], status)
        with patch('pathlib.Path.replace', side_effect=OSError('denied')), self.assertLogs(level='ERROR'):
            self.assertEqual(self.request('POST', json.dumps(values).encode())[0], 503)
        self.assertEqual(self.schedule.read(), values)
