"""Verify PNG uploads, stored references, screenshot delivery, and cleanup."""

from datetime import datetime, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import Mock, patch
import zlib

import pymysql

from mycount.activity.SaveMarketingPost import SaveMarketingPost
from mycount.constants.DMarketing import DMarketing
from mycount.entity.MarketingPost import MarketingPost
from mycount.interface.MarketingScreenshots import MarketingScreenshots
from mycount.interface.MarketingUpload import MarketingUpload
from mycount.server.ControlHandler import ControlHandler
from mycount.server.ControlPages import ControlPages


def png(extra: bytes = b"") -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + (chunk(b"tEXt", b"Comment\x00" + extra) if extra else b"")
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


def multipart(data: bytes | None, filename: str = "screenshot.png") -> tuple[bytes, str]:
    boundary = "mycount-test-boundary"
    parts = []
    for name, value in {"posted_at": "2026-10-03 14:05", "timezone_offset": "240",
                        "platform": "Reddit", "url": "https://reddit.com/r/example/",
                        "notes": "keep my notes"}.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    if data is not None:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="screenshot"; filename="{filename}"\r\nContent-Type: image/png\r\n\r\n'.encode() + data + b"\r\n")
    parts.append(f'--{boundary}--\r\n'.encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class MarketingScreenshotTests(unittest.TestCase):
    def test_png_validation_rejects_non_png_truncation_and_corruption(self):
        MarketingScreenshots.validate(png())
        for data in [b"not a PNG", b"\x89PNG\r\n\x1a\n", png()[:-1], png() + b"trailing bytes",
                     png()[:35] + bytes([png()[35] ^ 1]) + png()[36:]]:
            with self.subTest(data=data[:10]), self.assertRaises(ValueError):
                MarketingScreenshots.validate(data)
        with patch.object(DMarketing, "MAX_SCREENSHOT_BYTES", 10), self.assertRaisesRegex(ValueError, "10 MiB"):
            MarketingScreenshots.validate(png())

    def test_multipart_decoding_handles_large_upload_and_no_attachment(self):
        image = png(b"a" * 200000)
        body, content_type = multipart(image)
        fields, screenshot = MarketingUpload.parse(body, content_type)
        self.assertEqual(fields['platform'], ['Reddit'])
        self.assertEqual(screenshot, image)
        MarketingScreenshots.validate(screenshot)
        for data, filename in [(None, "screenshot.png"), (b"", "")]:
            fields, screenshot = MarketingUpload.parse(*multipart(data, filename))
            self.assertIsNone(screenshot)

    def test_generated_filenames_and_traversal_rejection(self):
        with TemporaryDirectory() as directory:
            files = MarketingScreenshots(Path(directory))
            first, second = files.save(png()), files.save(png())
            self.assertNotEqual(first, second)
            self.assertRegex(first, r'^pages/marketing/[0-9a-f]{32}\.png$')
            self.assertEqual(files.read(first), png())
            for reference in ['pages/marketing/../../secret.png', '/etc/passwd', 'pages/marketing/test.png']:
                with self.assertRaises(FileNotFoundError):
                    files.read(reference)

    def test_database_failure_removes_screenshot_and_preserves_cause(self):
        post = MarketingPost(datetime.now(timezone.utc), "X", "https://example.com/", "")
        with TemporaryDirectory() as directory:
            files = MarketingScreenshots(Path(directory))
            posts = Mock()
            error = pymysql.OperationalError("save failed")
            posts.record.side_effect = error
            with self.assertRaises(pymysql.OperationalError) as raised:
                SaveMarketingPost(posts, files).save(post, png())
            self.assertIs(raised.exception, error)
            self.assertEqual(list((Path(directory) / 'pages/marketing').iterdir()), [])

    def test_screenshot_display_and_posts_without_screenshots(self):
        post = {"id": 1, "posted_at": datetime(2026, 10, 3, 18, 5), "platform": "Reddit",
                "url": "https://example.com/", "notes": "", "screenshot_path": 'pages/marketing/' + 'a' * 32 + '.png'}
        body = ControlPages().marketing([post], []).decode()
        self.assertIn('enctype="multipart/form-data"', body)
        self.assertIn('name="screenshot" type="file"', body)
        self.assertIn('src="/' + post['screenshot_path'] + '"', body)
        self.assertIn('View Screenshot', body)
        post['screenshot_path'] = None
        self.assertNotIn('View Screenshot', ControlPages().marketing([post], []).decode())

    @patch('mycount.server.ControlHandler.DbMgr')
    def test_upload_fetch_invalid_upload_and_failed_save_cleanup(self, factory):
        with TemporaryDirectory() as directory, patch('mycount.server.ControlHandler.MarketingScreenshots') as screenshots:
            files = MarketingScreenshots(Path(directory))
            screenshots.return_value = files
            screenshots.validate.side_effect = MarketingScreenshots.validate
            with ThreadingHTTPServer(('127.0.0.1', 0), ControlHandler) as server:
                thread = Thread(target=server.serve_forever)
                thread.start()
                connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                try:
                    def upload(data, filename="screenshot.png"):
                        body, content_type = multipart(data, filename)
                        connection.request('POST', '/marketing', body, {'Content-Type': content_type})
                        response = connection.getresponse()
                        return response.status, response.read()

                    status, _ = upload(png(), "../../unsafe.png")
                    self.assertEqual(status, 303)
                    reference = factory.return_value.insert.call_args.args[1][-1]
                    self.assertEqual(files.read(reference), png())
                    factory.reset_mock()
                    connection.request('GET', '/' + reference)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.getheader('Content-Type'), 'image/png')
                    self.assertEqual(response.getheader('X-Content-Type-Options'), 'nosniff')
                    self.assertEqual(response.read(), png())
                    factory.assert_not_called()
                    for path in ['/pages/marketing/../../secret.png', '/pages/marketing/' + 'b' * 32 + '.png']:
                        connection.request('GET', path)
                        response = connection.getresponse()
                        self.assertEqual(response.status, 404)
                        response.read()
                    status, body = upload(b'invalid PNG')
                    self.assertEqual(status, 400)
                    self.assertIn(b'keep my notes', body)
                    factory.assert_not_called()
                    factory.return_value.insert.side_effect = pymysql.OperationalError('private error')
                    with self.assertLogs(level='ERROR'):
                        status, body = upload(png())
                    self.assertEqual(status, 503)
                    self.assertNotIn(b'private error', body)
                    self.assertEqual(len(list((Path(directory) / 'pages/marketing').iterdir())), 1)
                    factory.return_value.close.assert_called_once()
                    factory.reset_mock()
                    with patch.object(DMarketing, 'MAX_SCREENSHOT_BYTES', 10):
                        self.assertEqual(upload(png())[0], 400)
                    factory.assert_not_called()
                finally:
                    connection.close()
                    server.shutdown()
                    thread.join()
