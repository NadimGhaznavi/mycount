"""Verify control HTTP responses and deployed presentation assets."""

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


class ControlServerTests(unittest.TestCase):
    def test_banner_health_and_missing_page(self):
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
                    self.assertIn(b"MyCount <span>Control</span>", response.read())
                    connection.request("GET", "/health")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read()), {"status": "ok", "service": "mycount-control"})
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
                 "assert b'MyCount <span>Control</span>' in ControlPages().render()"],
                cwd=directory, check=True,
            )
