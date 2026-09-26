"""Integration checks against a disposable local MariaDB instance only."""

from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import pymysql

from mycount.activity.VisitorSchema import VisitorSchema
from mycount.interface.DbMgr import DbMgr


@unittest.skipUnless(shutil.which("mariadb-install-db") and shutil.which("mariadbd"),
                     "MariaDB server binaries are required for isolated integration tests")
class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="mycount-db-test-")
        cls.addClassCleanup(temporary.cleanup)
        root = Path(temporary.name)
        subprocess.run([
            "mariadb-install-db", "--no-defaults", f"--datadir={root / 'data'}",
            "--auth-root-authentication-method=normal", "--skip-test-db",
        ], check=True, capture_output=True, text=True, timeout=60)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        command = [
            "mariadbd", "--no-defaults", f"--datadir={root / 'data'}",
            f"--socket={root / 'db.sock'}", f"--pid-file={root / 'db.pid'}",
            f"--log-error={root / 'error.log'}", "--bind-address=127.0.0.1",
            f"--port={port}", "--innodb-buffer-pool-size=32M", "--skip-log-bin",
        ]
        if os.geteuid() == 0:
            command.append("--user=root")
        cls.server = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.addClassCleanup(cls.stop_server)
        deadline = time.monotonic() + 20
        while True:
            try:
                admin = pymysql.connect(host="127.0.0.1", port=port, user="root", autocommit=True)
                break
            except pymysql.OperationalError:
                if cls.server.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError((root / "error.log").read_text())
                time.sleep(0.1)
        try:
            with admin.cursor() as cursor:
                cursor.execute("CREATE DATABASE mycount")
                cursor.execute("CREATE USER 'mycount'@'127.0.0.1' IDENTIFIED BY 'test-only'")
                cursor.execute("GRANT ALL ON mycount.* TO 'mycount'@'127.0.0.1'")
        finally:
            admin.close()
        environment = patch.dict(os.environ, {
            "DB_HOST": "127.0.0.1", "DB_PORT": str(port), "DB_USER": "mycount",
            "DB_PASSWORD": "test-only", "DB_NAME": "mycount",
        })
        environment.start()
        cls.addClassCleanup(environment.stop)
        cls.db = DbMgr()
        cls.addClassCleanup(cls.db.close)
        if cls.db.query("SHOW TABLES"):
            raise AssertionError("DbMgr must not initialize the schema")
        VisitorSchema(cls.db).apply()

    @classmethod
    def stop_server(cls):
        cls.server.terminate()
        try:
            cls.server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.wait(timeout=5)

    def tearDown(self):
        self.db.execute("DELETE FROM page_views")
        self.db.execute("DELETE FROM pages")

    def page(self, url="https://example.com/products/", site="mycount"):
        return self.db.insert("INSERT INTO pages(site, url) VALUES (%s, %s)", (site, url))

    def view(self, page_id):
        return self.db.insert("INSERT INTO page_views(page_id) VALUES (%s)", (page_id,))

    def test_schema_rerun_preserves_records_and_utc(self):
        page_id = self.page()
        view_id = self.view(page_id)
        self.db.execute("INSERT INTO page_view_languages VALUES (%s, 1, 'en-CA')", (view_id,))
        VisitorSchema(self.db).apply()
        row = self.db.query("SELECT * FROM page_views WHERE page_view_id = %s", (view_id,))[0]
        self.assertEqual(row["page_id"], page_id)
        self.assertIsNone(row["fingerprint"])
        self.assertLess(abs((datetime.now(timezone.utc).replace(tzinfo=None) - row["received_at"]).total_seconds()), 5)
        self.assertEqual(self.db.query("SELECT language_tag FROM page_view_languages"), [{"language_tag": "en-CA"}])

    def test_full_url_identity_is_case_sensitive_and_site_scoped(self):
        url = "https://example.com/" + "x" * 3000 + "é"
        self.page(url)
        with self.assertRaises(pymysql.IntegrityError):
            self.page(url)
        for distinct in (url + "/", url[:-1] + "É", url + "other"):
            self.page(distinct)
        self.page(url, "another-site")
        row = self.db.query("SELECT url, url_hash FROM pages ORDER BY page_id LIMIT 1")[0]
        self.assertEqual(row["url"], url)
        self.assertEqual(row["url_hash"], sha256(url.encode()).digest())
        self.assertEqual(self.db.query("SELECT COUNT(*) AS n FROM pages")[0]["n"], 5)

    def test_view_and_languages_roll_back_together(self):
        page_id = self.page()
        with self.assertRaises(pymysql.IntegrityError):
            with self.db.transaction():
                view_id = self.view(page_id)
                self.db.execute("INSERT INTO page_view_languages VALUES (%s, 1, 'en')", (view_id,))
                self.db.execute("INSERT INTO page_view_languages VALUES (%s, 1, 'fr')", (view_id,))
        self.assertEqual(self.db.query("SELECT * FROM page_views"), [])
        self.assertEqual(self.db.query("SELECT * FROM page_view_languages"), [])

    def test_bound_values_commit_and_are_visible_to_another_connection(self):
        url = "https://example.com/quote'; DROP TABLE pages; --"
        with self.db.transaction():
            page_id = self.page(url)
            view_id = self.view(page_id)
            for position, tag in ((2, "fr"), (1, "en-CA")):
                self.db.execute("INSERT INTO page_view_languages VALUES (%s, %s, %s)", (view_id, position, tag))
        reader = DbMgr()
        try:
            self.assertEqual(reader.query("SELECT url FROM pages")[0]["url"], url)
            self.assertEqual(reader.query("SELECT language_tag FROM page_view_languages ORDER BY preference_order"),
                             [{"language_tag": "en-CA"}, {"language_tag": "fr"}])
        finally:
            reader.close()

    def test_foreign_keys_and_language_cleanup(self):
        with self.assertRaises(pymysql.IntegrityError):
            self.view(0)
        page_id = self.page()
        view_id = self.view(page_id)
        self.db.execute("INSERT INTO page_view_languages VALUES (%s, 1, 'en')", (view_id,))
        with self.assertRaises(pymysql.IntegrityError):
            self.db.execute("DELETE FROM pages WHERE page_id = %s", (page_id,))
        self.db.execute("DELETE FROM page_views WHERE page_view_id = %s", (view_id,))
        self.assertEqual(self.db.query("SELECT * FROM page_view_languages"), [])

    def test_fingerprint_pair_and_reporting(self):
        page_id = self.page()
        fingerprint = sha256(b"test browser").digest()
        for digest, version in ((fingerprint, None), (None, 1), (fingerprint, 0)):
            with self.subTest(version=version, present=digest is not None):
                with self.assertRaises(pymysql.OperationalError) as raised:
                    self.db.execute("INSERT INTO page_views(page_id, fingerprint, fingerprint_version) VALUES (%s, %s, %s)",
                                    (page_id, digest, version))
                self.assertEqual(raised.exception.args[0], 4025)
        for version in (1, 1, 2):
            self.db.execute("INSERT INTO page_views(page_id, fingerprint, fingerprint_version) VALUES (%s, %s, %s)",
                            (page_id, fingerprint, version))
        self.view(page_id)
        counts = self.db.query("SELECT COUNT(*) AS views, COUNT(DISTINCT fingerprint_version, fingerprint) AS browsers FROM page_views")[0]
        self.assertEqual(counts, {"views": 4, "browsers": 2})

    def test_read_only_transaction_rejects_writes_and_recovers(self):
        with self.assertRaises(pymysql.OperationalError):
            with self.db.transaction(read_only=True):
                self.page()
        with self.db.transaction():
            self.page()
        self.assertEqual(self.db.query("SELECT COUNT(*) AS n FROM pages")[0]["n"], 1)
