"""Validate promotional event inputs and the control form save boundary."""

from datetime import datetime, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import pymysql

from mycount.constants.DMarketing import DMarketing
from mycount.interface.MarketingForm import MarketingForm
from mycount.server.ControlHandler import ControlHandler
from mycount.server.ControlPages import ControlPages
from mycount.entity.Report import Report
from mycount.interface.ReportQuery import ReportQuery
from mycount.interface.DbCommitUncertain import DbCommitUncertain


class MarketingTests(unittest.TestCase):
    def fields(self, **changes):
        return {key: [value] for key, value in {
            "posted_at": "2026-10-03 14:05", "timezone_offset": "240",
            "platform": "Reddit", "url": "https://reddit.com/r/example/comments/123",
            "notes": "A promotional post", "submission_id": "a" * 32, **changes,
        }.items()}

    def test_local_timestamp_conversion_and_optional_notes(self):
        for offset, expected in [(240, datetime(2026, 10, 3, 18, 5, tzinfo=timezone.utc)),
                                 (-330, datetime(2026, 10, 3, 8, 35, tzinfo=timezone.utc))]:
            post = MarketingForm.parse(self.fields(timezone_offset=str(offset), notes=""))
            self.assertEqual(post.posted_at, expected)
            self.assertEqual(post.notes, "")

    def test_invalid_external_fields_are_rejected(self):
        for change in [dict(posted_at="2026-02-30 12:00"), dict(posted_at="2026-1-03 14:05"),
                       dict(timezone_offset=""), dict(timezone_offset="841"), dict(platform="Unsupported"),
                       dict(url="javascript:alert(1)"), dict(url="https://"),
                       dict(url="https://example.com:bad"), dict(url="https://example.com/a b"),
                       dict(url="https://example.com/\x00hidden"), dict(created_at="2026-10-03"),
                       dict(url="https://example.com/" + "a" * 2048), dict(notes="a" * 4001),
                       dict(submission_id=""), dict(submission_id="A" * 32)]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                MarketingForm.parse(self.fields(**change))
        fields = self.fields()
        fields["platform"].append("X")
        with self.assertRaises(ValueError):
            MarketingForm.parse(fields)

    def test_form_choices_and_saved_event_escaping(self):
        post = {"id": 1, "posted_at": datetime(2026, 10, 3, 18, 5), "platform": "Reddit",
                "url": "https://example.com/?a=1&b=2", "notes": "<script>alert(1)</script>", "screenshot_path": None}
        body = ControlPages().marketing(Report(ReportQuery.resolve({}), [{"day": "2026-10-03", "page_views": 1}], None, posts=[post])).decode()
        self.assertEqual(DMarketing.PLATFORMS, tuple(sorted(DMarketing.PLATFORMS)))
        indices = [body.index(f'<option value="{platform}"') for platform in DMarketing.PLATFORMS]
        self.assertEqual(indices, sorted(indices))
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', body)
        self.assertNotIn('name="created_at"', body)
        self.assertIn('"posted_at": "2026-10-03T18:05:00+00:00"', body)
        self.assertIn("Plotly.newPlot('marketing-traffic'", body)

    @patch("mycount.server.ControlHandler.DbMgr")
    def test_save_redirect_validation_and_database_failure(self, factory):
        factory.return_value.query.return_value = []
        with patch("mycount.activity.ReadReports.DbMgr", factory), ThreadingHTTPServer(("127.0.0.1", 0), ControlHandler) as server:
            thread = Thread(target=server.serve_forever)
            thread.start()
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            self.addCleanup(connection.close)
            try:
                def submit(fields, **headers):
                    body = urlencode({key: values[0] for key, values in fields.items()})
                    connection.request("POST", "/marketing", body,
                                       {"Content-Type": "application/x-www-form-urlencoded", **headers})
                    response = connection.getresponse()
                    result = (response.status, response.getheader("Location"), response.read())
                    return result

                status, location, body = submit(self.fields())
                self.assertEqual((status, location), (303, "/marketing?saved=1"))
                args = factory.return_value.insert.call_args.args
                self.assertEqual(args[1][0], datetime(2026, 10, 3, 18, 5))
                self.assertNotIn('created_at', args[0])
                factory.return_value.transaction.assert_called_once_with()
                factory.return_value.close.assert_called_once()
                factory.reset_mock()
                self.assertEqual(submit(self.fields(platform="invalid"))[0], 400)
                factory.assert_not_called()
                self.assertEqual(submit(self.fields(), Origin="https://other.example")[0], 403)
                self.assertEqual(submit(self.fields(), Origin="https://[")[0], 403)
                self.assertEqual(submit(self.fields(), Origin="null")[0], 403)
                self.assertEqual(submit(self.fields(), **{"Transfer-Encoding": "chunked"})[0], 400)
                factory.assert_not_called()
                factory.return_value.insert.side_effect = pymysql.OperationalError("private details")
                with self.assertLogs(level="ERROR"):
                    status, location, body = submit(self.fields(notes="keep these notes"))
                self.assertEqual(status, 503)
                self.assertIn(b'keep these notes', body)
                self.assertNotIn(b'private details', body)
                factory.return_value.close.assert_called_once()
                factory.reset_mock()
                factory.return_value.insert.side_effect = DbCommitUncertain(2013, "private details")
                with self.assertLogs(level="ERROR"):
                    status, location, body = submit(self.fields())
                self.assertEqual(status, 503)
                self.assertIn(b'name="submission_id" value="' + b'a' * 32 + b'"', body)
                self.assertIn(b'Retry this form to confirm the same posting.', body)
                self.assertNotIn(b'window.location.replace', body)
                self.assertNotIn(b'private details', body)
                factory.reset_mock()
                factory.return_value.query.side_effect = pymysql.OperationalError("private details")
                with self.assertLogs(level="ERROR"):
                    connection.request("GET", "/marketing")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 503)
                    self.assertIn(b'Marketing data unavailable.', response.read())
                factory.return_value.close.assert_called_once()
            finally:
                server.shutdown()
                thread.join()
