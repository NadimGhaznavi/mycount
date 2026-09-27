"""Integration checks against a disposable local MariaDB instance only."""

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import pymysql

from mycount.activity.VisitorSchema import VisitorSchema
from mycount.interface.DbMgr import DbMgr
from mycount.activity.GeoIpSchema import GeoIpSchema
from mycount.activity.UpdateGeoIp import UpdateGeoIp
from mycount.interface.GeoIp import GeoIp
from mycount.interface.GeoIpImportDb import GeoIpImportDb
from mycount.interface.VisitDb import VisitDb
from mycount.entity.Visit import Visit
from mycount.interface.VisitPayload import VisitPayload
from mycount.activity.BrowserMetadata import BrowserMetadata
from test_geoip import FixtureGeoIpSource, archive


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
        GeoIpSchema(cls.db).apply()

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
        self.db.execute("DELETE FROM geoip_ranges")

    def test_geoip_refresh_and_both_address_families(self):
        counts = UpdateGeoIp(FixtureGeoIpSource(), GeoIpImportDb(self.db)).run()
        self.assertEqual(counts, {4: 1, 6: 2})
        reader = DbMgr()
        try:
            geo = GeoIp(reader)
            for ip in ("8.8.8.0", "8.8.8.255", "::ffff:8.8.8.8", "2606:4700::1"):
                self.assertEqual(geo.locate(ip).city_name, "Example")
            self.assertEqual(geo.locate("2606:4700:10::1").city_name, "Specific")
            # A gap after the nested range must still match the enclosing range.
            self.assertEqual(geo.locate("2606:4700:10::100").city_name, "Example")
            for ip in ("8.8.9.0", "127.0.0.1", "::1", "2607::1"):
                self.assertIsNone(geo.locate(ip).country_code)
        finally:
            reader.close()
        UpdateGeoIp(FixtureGeoIpSource(city="Updated"), GeoIpImportDb(self.db)).run()
        self.assertEqual(GeoIp(self.db).locate("8.8.8.8").city_name, "Updated")

    def test_failed_second_download_preserves_both_active_families(self):
        database = GeoIpImportDb(self.db)
        UpdateGeoIp(FixtureGeoIpSource(city="Original"), database).run()
        with self.assertRaises(OSError):
            UpdateGeoIp(FixtureGeoIpSource(fail_version=6, city="New"), database).run()
        self.assertEqual(GeoIp(self.db).locate("8.8.8.8").city_name, "Original")
        self.assertEqual(GeoIp(self.db).locate("2606:4700::1").city_name, "Original")
        self.assertEqual(self.db.query("SHOW TABLES LIKE 'geoip_ranges_next'"), [])
        # The lock is released even after failure, allowing the next update.
        UpdateGeoIp(FixtureGeoIpSource(city="Retry"), database).run()
        self.assertEqual(GeoIp(self.db).locate("8.8.8.8").city_name, "Retry")

    def test_empty_second_file_does_not_publish(self):
        class EmptySource(FixtureGeoIpSource):
            def download(self, version, destination):
                if version == 6:
                    archive(destination, version, [])
                else:
                    super().download(version, destination)
        with self.assertRaisesRegex(ValueError, "empty"):
            UpdateGeoIp(EmptySource(), GeoIpImportDb(self.db)).run()
        self.assertEqual(self.db.query("SELECT * FROM geoip_ranges"), [])

    def test_geoip_refresh_lock_excludes_another_connection(self):
        reader = DbMgr()
        try:
            with GeoIpImportDb(self.db).refresh():
                with self.assertRaisesRegex(RuntimeError, "already running"):
                    with GeoIpImportDb(reader).refresh():
                        self.fail("A second importer entered the refresh")
        finally:
            reader.close()

    def test_city_migration_and_visit_round_trip(self):
        self.db.execute("ALTER TABLE page_views MODIFY city_name VARCHAR(128) NULL")
        view_id = self.view(self.page())
        VisitorSchema(self.db).apply()
        self.assertEqual(self.db.query("SELECT page_view_id FROM page_views")[0]["page_view_id"], view_id)
        city = "É" * 137
        visit = Visit(site="mycount", url="https://example.com/other", received_at=datetime.now(timezone.utc),
                      city_name=city, languages=("en-CA", "fr"))
        first = VisitDb(self.db).record(visit)
        second = VisitDb(self.db).record(visit)
        rows = self.db.query("SELECT page_id, city_name FROM page_views WHERE page_view_id IN (%s, %s)", (first, second))
        self.assertEqual(rows[0], rows[1])
        self.assertEqual(rows[0]["city_name"], city)
        self.assertEqual(self.db.query("SELECT COUNT(*) AS n FROM page_view_languages")[0]["n"], 4)

    def test_visitor_details_migration_preserves_old_rows_and_new_round_trip(self):
        columns = ('referrer_host', 'user_agent', 'browser_version', 'os_version',
                   'device_brand', 'device_model', 'is_bot', 'client_details')
        self.db.execute('ALTER TABLE page_views ' + ', '.join('DROP COLUMN ' + name for name in columns))
        old_id = self.view(self.page())
        VisitorSchema(self.db).apply()
        VisitorSchema(self.db).apply()
        old = self.db.query('SELECT * FROM page_views WHERE page_view_id=%s', (old_id,))[0]
        for column in columns:
            self.assertIsNone(old[column])
        payload = {
            'schema_version': 1, 'event': 'page_view', 'site': 'r3el',
            'url': 'https://r3el.osoyalce.com/', 'languages': ['en-CA'],
            'user_agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'referrer': 'https://example.com/search?private=value',
            'client_details': {'timezone': 'America/Toronto', 'viewport_width': 1280, 'webdriver': False},
        }
        visit, agent = VisitPayload().resolve(payload, 'https://r3el.osoyalce.com')
        visit = BrowserMetadata().enrich(visit, agent)
        view_id = VisitDb(self.db).record(visit)
        row = self.db.query('SELECT * FROM page_views WHERE page_view_id=%s', (view_id,))[0]
        self.assertEqual(row['referrer_host'], 'example.com')
        self.assertEqual(row['user_agent'], payload['user_agent'])
        self.assertEqual(row['browser_version'], '130.0.0')
        self.assertEqual(row['is_bot'], 0)
        self.assertEqual(json.loads(row['client_details']), payload['client_details'])

    def test_visit_details_roll_back_with_invalid_languages(self):
        visit = Visit(site='r3el', url='https://r3el.osoyalce.com/',
                      received_at=datetime.now(timezone.utc), referrer_host='example.com',
                      client_details=(('timezone', 'America/Toronto'),), languages=('x' * 256,))
        with self.assertRaises(pymysql.DataError):
            VisitDb(self.db).record(visit)
        self.assertEqual(self.db.query('SELECT * FROM page_views'), [])
        self.assertEqual(self.db.query('SELECT * FROM pages'), [])

    def test_visitor_id_migration_preserves_unknown_history(self):
        self.db.execute('ALTER TABLE page_views DROP INDEX idx_view_visitor_time, DROP COLUMN visitor_id')
        old_id = self.view(self.page())
        VisitorSchema(self.db).apply()
        VisitorSchema(self.db).apply()
        row = self.db.query('SELECT visitor_id FROM page_views WHERE page_view_id=%s', (old_id,))[0]
        self.assertIsNone(row['visitor_id'])
        self.assertEqual(VisitDb(self.db).totals_by_site(), [{
            'site': 'mycount', 'page_views': 1, 'unique_browsers': 0,
            'unidentified_views': 1, 'known_bot_views': 0,
            'last_visited': self.db.query('SELECT received_at FROM page_views WHERE page_view_id=%s', (old_id,))[0]['received_at'],
        }])

    def test_unique_browsers_deduplicate_reloads_and_pages_with_site_scoping(self):
        visits = VisitDb(self.db)
        self.assertEqual(visits.totals_by_site(), [])
        identifier = uuid4().bytes
        visit = Visit(site='r3el', url='https://r3el.osoyalce.com/',
                      received_at=datetime.now(timezone.utc), visitor_id=identifier)
        first = visits.record(visit)
        visits.record(visit)
        visits.record(replace(visit, url='https://r3el.osoyalce.com/about'))
        visits.record(replace(visit, visitor_id=uuid4().bytes))
        visits.record(replace(visit, visitor_id=None, is_bot=True))
        visits.record(replace(visit, site='ax3l', url='https://ax3l.osoyalce.com/'))
        self.assertEqual(self.db.query('SELECT visitor_id FROM page_views WHERE page_view_id=%s',
                                      (first,))[0]['visitor_id'], identifier)
        self.assertEqual(visits.totals_by_site(), [
            {'site': 'r3el', 'page_views': 5, 'unique_browsers': 2,
             'unidentified_views': 1, 'known_bot_views': 1,
             'last_visited': visit.received_at.replace(tzinfo=None)},
            {'site': 'ax3l', 'page_views': 1, 'unique_browsers': 1,
             'unidentified_views': 0, 'known_bot_views': 0,
             'last_visited': visit.received_at.replace(tzinfo=None)},
        ])

    def test_site_last_visit_uses_latest_time_across_pages(self):
        visits = VisitDb(self.db)
        latest = datetime(2026, 9, 27, 15, 5, tzinfo=timezone.utc)
        visits.record(Visit(site='example', url='https://example.com/new', received_at=latest))
        visits.record(Visit(site='example', url='https://example.com/old',
                            received_at=datetime(2026, 9, 26, tzinfo=timezone.utc)))
        rows = visits.totals_by_site()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['page_views'], 2)
        self.assertEqual(rows[0]['last_visited'], latest.replace(tzinfo=None))

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
