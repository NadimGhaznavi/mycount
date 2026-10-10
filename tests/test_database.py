"""Integration checks against a disposable local MariaDB instance only."""

from dataclasses import replace
from datetime import date, datetime, timezone
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
from mycount.interface.VisitDb import VisitDb
from mycount.interface.MarketingDb import MarketingDb
from mycount.entity.MarketingPost import MarketingPost
from mycount.entity.Visit import Visit
from mycount.interface.VisitPayload import VisitPayload
from mycount.activity.BrowserMetadata import BrowserMetadata
from mycount.activity.SaveMarketingPost import SaveMarketingPost
from mycount.entity.ReportOptions import ReportOptions
from mycount.interface.DbCommitUncertain import DbCommitUncertain
from mycount.interface.MarketingScreenshots import MarketingScreenshots


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
        if cls.db.query("SHOW TABLES LIKE 'geoip_ranges'"):
            raise AssertionError("MyCount must not create local GeoIP range tables")

    @classmethod
    def stop_server(cls):
        cls.server.terminate()
        try:
            cls.server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.wait(timeout=5)

    def tearDown(self):
        self.db.execute("DELETE FROM marketing_posts")
        self.db.execute("DELETE FROM page_views")
        self.db.execute("DELETE FROM pages")

    def test_marketing_posts_persist_and_schema_reapplication_preserves_them(self):
        marketing = MarketingDb(self.db)
        posted_at = datetime(2026, 10, 3, 18, 5, tzinfo=timezone.utc)
        post = MarketingPost(posted_at, "Reddit", "https://reddit.com/r/example/", "Some notes")
        before = self.db.query("SELECT UTC_TIMESTAMP(6) AS now")[0]['now']
        first = marketing.record(post)
        second = marketing.record(replace(post, notes="", submission_id=uuid4().hex))
        VisitorSchema(self.db).apply()
        VisitorSchema(self.db).apply()
        rows = marketing.posts()
        self.assertEqual([row['id'] for row in rows], [second, first])
        self.assertEqual(rows[1]['posted_at'], posted_at.replace(tzinfo=None))
        self.assertEqual(rows[1]['notes'], "Some notes")
        self.assertEqual(rows[0]['notes'], "")
        self.assertIsNone(rows[0]['screenshot_path'])
        self.assertGreaterEqual(rows[1]['created_at'], before)
        self.db.execute("ALTER TABLE marketing_posts DROP COLUMN screenshot_path")
        VisitorSchema(self.db).apply()
        self.assertIsNone(marketing.posts()[0]['screenshot_path'])
        reference = "pages/marketing/" + "a" * 32 + ".png"
        image_post = marketing.record(replace(post, screenshot_path=reference, submission_id=uuid4().hex))
        VisitorSchema(self.db).apply()
        self.assertEqual(marketing.posts()[0]['id'], image_post)
        self.assertEqual(marketing.posts()[0]['screenshot_path'], reference)

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

    def test_lost_commit_reply_keeps_committed_screenshot_and_retry_deduplicates(self):
        marketing = MarketingDb(self.db)
        post = MarketingPost(datetime.now(timezone.utc), 'X', 'https://example.com/', 'Original')
        commit = self.db._connection.commit

        def lost_reply():
            commit()
            raise pymysql.OperationalError(2013, 'Lost commit reply')

        with tempfile.TemporaryDirectory() as directory:
            screenshots = MarketingScreenshots(Path(directory))
            saver = SaveMarketingPost(marketing, screenshots)
            with patch.object(self.db._connection, 'commit', side_effect=lost_reply):
                with self.assertRaises(DbCommitUncertain):
                    saver.save(post, b'image')
            rows = marketing.posts()
            self.assertEqual(len(rows), 1)
            self.assertEqual(screenshots.read(rows[0]['screenshot_path']), b'image')
            self.assertEqual(saver.save(post, b'reselected'), rows[0]['id'])
            # The unique database constraint also handles simultaneous submissions.
            self.assertEqual(marketing.record(replace(post, notes='Changed')), rows[0]['id'])
            self.assertEqual(marketing.posts()[0]['notes'], 'Original')
            self.assertEqual(len(list((Path(directory) / 'pages/marketing').iterdir())), 1)

    def test_submission_migration_preserves_legacy_posts(self):
        self.db.execute('ALTER TABLE marketing_posts DROP INDEX uq_marketing_submission, DROP COLUMN submission_id')
        identifier = self.db.insert("INSERT INTO marketing_posts(posted_at, platform, url, notes) "
                                    "VALUES (UTC_TIMESTAMP(), 'X', 'https://example.com/', '')")
        VisitorSchema(self.db).apply()
        VisitorSchema(self.db).apply()
        self.assertEqual(self.db.query('SELECT id, submission_id FROM marketing_posts'),
                         [dict(id=identifier, submission_id=None)])

    def test_visitor_records_cover_schema_and_filter_before_pagination(self):
        visits = VisitDb(self.db)
        timestamp = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
        base = Visit(site='mycount_smoke_visitors', url='https://example.com/50%_=',
                     received_at=timestamp, country_name='Canada', city_name='Toronto',
                     visitor_id=bytes.fromhex('AB' * 16), is_bot=True,
                     client_details=(('timezone', 'America/Toronto'),))
        first = visits.record(base)
        second = visits.record(base)
        visits.record(replace(base, url='https://example.com/other'))
        rows = visits.visitor_records({'url': '50%_=', 'city_name': 'Toronto'}, limit=1)
        self.assertEqual(rows[0]['page_view_id'], second)
        self.assertEqual(rows[0]['visitor_id'], 'AB' * 16)
        self.assertEqual(rows[0]['is_bot'], 1)
        columns = {column['Field'] for column in self.db.query('SHOW COLUMNS FROM page_views')}
        self.assertEqual(set(rows[0]), columns | {'site', 'url'})
        older = visits.visitor_records({'url': '50%_='},
                                      before=(rows[0]['received_at'], second), limit=1)
        self.assertEqual(older[0]['page_view_id'], first)
        self.assertEqual(visits.visitor_records({'site': "' OR 1=1 --"}), [])
        self.assertEqual(len(visits.visitor_records({'visitor_id': 'AB' * 16})), 3)
        self.assertEqual(len(visits.visitor_records({'client_details': 'America/Toronto'})), 3)

    def test_daily_totals_use_local_dst_boundaries_and_include_empty_days(self):
        visits = VisitDb(self.db)
        options = ReportOptions(date(2026, 3, 7), date(2026, 3, 10), 'America/Toronto')
        base = Visit(site='example', url='https://example.com/', received_at=datetime.now(timezone.utc))
        for timestamp, bot in [
            (datetime(2026, 3, 7, 4, 59), False),  # Before the selected range.
            (datetime(2026, 3, 7, 5), False),
            (datetime(2026, 3, 8, 4, 59), False),
            (datetime(2026, 3, 8, 5), False),
            (datetime(2026, 3, 8, 7, 30), False),
            (datetime(2026, 3, 9, 3, 59), False),
            (datetime(2026, 3, 9, 4), True),
            (datetime(2026, 3, 10, 4), False),
            (datetime(2026, 3, 11, 4), False),  # Exclusive end.
        ]:
            visits.record(replace(base, received_at=timestamp.replace(tzinfo=timezone.utc), is_bot=bot))
        daily = visits.daily_totals(options.day_ranges(), exclude_bots=True)
        self.assertEqual(daily, [dict(day=day, page_views=count) for day, count in
                                [('2026-03-07', 2), ('2026-03-08', 3), ('2026-03-09', 0), ('2026-03-10', 1)]])
        days = options.day_ranges()
        filters = dict(start=days[0][1], end=days[-1][2], exclude_bots=True)
        for query in (visits.totals_by_site, visits.totals_by_page, visits.totals_by_location, visits.totals_by_referrer):
            self.assertEqual(sum(row['page_views'] for row in query(**filters)), 6)
        self.assertEqual(visits.daily_totals(days, exclude_bots=False)[2]['page_views'], 1)

    def test_recent_visit_pages_break_ties_without_skipping_or_duplicating_rows(self):
        visits = VisitDb(self.db)
        timestamp = datetime(2026, 3, 8, 12, tzinfo=timezone.utc)
        visit = Visit(site='example', url='https://example.com/', received_at=timestamp)
        identifiers = [visits.record(visit) for _ in range(120)]
        first = visits.recent_visits()
        self.assertEqual(len(first), 50)
        cursor = first[-1]['received_at'], first[-1]['page_view_id']
        visits.record(visit)  # A new visit must not shift the older-page position.
        second = visits.recent_visits(before=cursor)
        cursor = second[-1]['received_at'], second[-1]['page_view_id']
        third = visits.recent_visits(before=cursor)
        self.assertEqual([row['page_view_id'] for row in first + second + third], list(reversed(identifiers)))

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

    def test_collection_additions_migrate_and_preserve_exact_values(self):
        self.db.execute('ALTER TABLE page_views DROP COLUMN search, DROP COLUMN referrer')
        old_id = self.view(self.page())
        VisitorSchema(self.db).apply()
        VisitorSchema(self.db).apply()
        self.assertEqual(self.db.query(
            'SELECT search, referrer FROM page_views WHERE page_view_id=%s', (old_id,)
        )[0], dict(search=None, referrer=None))
        expected = dict(search='?q=a%20b&q=two&empty=',
                        referrer='https://example.com/path?q=a%20b#section')
        visit = Visit(site='mycount', url='https://example.com/page',
                      received_at=datetime.now(timezone.utc), **expected)
        first = VisitDb(self.db).record(visit)
        second = VisitDb(self.db).record(replace(visit, search='?other=yes'))
        self.assertEqual(self.db.query(
            'SELECT search, referrer FROM page_views WHERE page_view_id=%s', (first,)
        )[0], expected)
        rows = self.db.query('SELECT page_id FROM page_views WHERE page_view_id IN (%s,%s)', (first, second))
        self.assertEqual(rows[0]['page_id'], rows[1]['page_id'])

    def test_country_backfill_batches_resume_after_failure(self):
        from mycount.interface.CountryNameMigration import CountryNameMigration
        from mycount.constants.DCountryNameMigration import DCountryNameMigration

        for _ in range(3):
            VisitDb(self.db).record(Visit(site='example', url='https://example.com/',
                                        received_at=datetime.now(timezone.utc), country_code='CA'))
        execute = self.db.execute
        batches = 0

        def fail_second_batch(sql, params=()):
            nonlocal batches
            if 'UPDATE page_views' in sql:
                batches += 1
                if batches == 2:
                    raise RuntimeError('interrupted batch')
            return execute(sql, params)

        with patch.object(DCountryNameMigration, 'BATCH_SIZE', 1):
            with patch.object(self.db, 'execute', side_effect=fail_second_batch):
                with self.assertRaisesRegex(RuntimeError, 'interrupted batch'):
                    CountryNameMigration(self.db).apply()
            self.assertEqual(self.db.query(
                'SELECT COUNT(*) AS total FROM page_views WHERE country_name IS NOT NULL'
            )[0]['total'], 1)
            CountryNameMigration(self.db).apply()
            self.assertEqual(self.db.query(
                "SELECT COUNT(*) AS total FROM page_views WHERE country_name='Canada'"
            )[0]['total'], 3)
            CountryNameMigration(self.db).apply()

    def test_country_name_migration_and_continent_removal(self):
        visits = VisitDb(self.db)
        visit = Visit(site='example', url='https://example.com/',
                      received_at=datetime.now(timezone.utc), country_code='CA')
        known = visits.record(visit)
        unknown = visits.record(replace(visit, country_code='ZZ'))
        missing = visits.record(replace(visit, country_code=None))
        for table in ('page_views',):
            self.db.execute(f'ALTER TABLE {table} DROP COLUMN country_name, ADD COLUMN continent VARCHAR(64) NULL')
        for _ in range(2):
            VisitorSchema(self.db).apply()
        rows = self.db.query('SELECT page_view_id, country_name FROM page_views')
        self.assertEqual({row['page_view_id']: row['country_name'] for row in rows},
                         {known: 'Canada', unknown: None, missing: None})
        for table in ('page_views',):
            self.assertNotIn('continent', {row['Field'] for row in self.db.query(f'SHOW COLUMNS FROM {table}')})
        supplied = visits.record(replace(visit, country_name='Provider name'))
        VisitorSchema(self.db).apply()
        self.assertEqual(self.db.query('SELECT country_name FROM page_views WHERE page_view_id=%s',
                                      (supplied,))[0]['country_name'], 'Provider name')

    def test_geoip_details_migration_and_visit_round_trip(self):
        old_id = self.view(self.page())
        for table in ('page_views',):
            self.db.execute(f'ALTER TABLE {table} DROP COLUMN latitude, DROP COLUMN longitude, '
                            'DROP COLUMN zip, DROP COLUMN timezone')
        for _ in range(2):
            VisitorSchema(self.db).apply()
        from mycount.entity.GeoLocation import GeoLocation
        location = GeoLocation(city_name='Example', latitude=43.2557, longitude=-79.8711,
                               zip='00123', timezone='America/Toronto')
        for latitude, longitude in ((location.latitude, location.longitude), (0.0, None), (None, 0.0)):
            view_id = VisitDb(self.db).record(Visit(
                site='mycount', url='https://example.com/', received_at=datetime.now(timezone.utc),
                latitude=latitude, longitude=longitude, zip=location.zip, timezone=location.timezone,
                client_details=(('timezone', 'Europe/London'),),
            ))
            self.assertEqual(self.db.query(
                'SELECT latitude, longitude FROM page_views WHERE page_view_id=%s', (view_id,)
            )[0], dict(latitude=latitude, longitude=longitude))
            row = self.db.query('SELECT zip, timezone, client_details FROM page_views WHERE page_view_id=%s',
                                (view_id,))[0]
            self.assertEqual(row['zip'], '00123')
            self.assertEqual(row['timezone'], 'America/Toronto')
            self.assertEqual(json.loads(row['client_details'])['timezone'], 'Europe/London')
        self.assertEqual(self.db.query(
            'SELECT latitude, longitude, zip, timezone FROM page_views WHERE page_view_id=%s', (old_id,)
        )[0], dict(latitude=None, longitude=None, zip=None, timezone=None))

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

    def test_page_metrics_rank_views_and_keep_sites_separate(self):
        visits = VisitDb(self.db)
        self.assertEqual(visits.totals_by_page(), [])
        latest = datetime(2026, 9, 27, 15, 5, tzinfo=timezone.utc)
        old = datetime(2026, 9, 26, tzinfo=timezone.utc)
        for site, url, times in (
            ('first', 'https://example.com/z', [old, latest, old]),
            ('first', 'https://example.com/b', [old]),
            ('first', 'https://example.com/a', [latest]),
            ('second', 'https://example.com/z', [old]),
        ):
            for timestamp in times:
                visits.record(Visit(site=site, url=url, received_at=timestamp))
        rows = visits.totals_by_page()
        self.assertEqual([(row['site'], row['url'], row['page_views']) for row in rows], [
            ('first', 'https://example.com/z', 3),
            ('first', 'https://example.com/a', 1),
            ('first', 'https://example.com/b', 1),
            ('second', 'https://example.com/z', 1),
        ])
        self.assertEqual(rows[0]['last_visited'], latest.replace(tzinfo=None))
        self.assertEqual(rows[-1]['last_visited'], old.replace(tzinfo=None))

    def test_bot_filter_applies_to_all_metrics_and_last_visited(self):
        visits = VisitDb(self.db)
        visit = Visit(site='example', url='https://example.com/',
                      received_at=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
                      country_code='CA', country_name='Canada', city_name='Hamilton')
        visits.record(replace(visit, is_bot=False, browser_family='Chrome'))
        visits.record(visit)  # Unknown does not mean bot.
        for flag, family in [(True, 'Other'), (False, 'GoogleOther'),
                             (None, 'GoogleOther'), (None, 'Googlebot'),
                             (False, 'Bytespider'), (None, 'Bytespider')]:
            visits.record(replace(visit, is_bot=flag, browser_family=family,
                                 received_at=datetime(2026, 9, 27, 18, tzinfo=timezone.utc)))
        visits.record(replace(visit, site='bot-only', url='https://example.com/bot',
                             city_name='Mountain View', is_bot=True))
        self.assertEqual(visits.count_by_site('example'), 2)
        self.assertEqual(visits.count_by_site('bot-only'), 0)
        self.assertEqual(visits.count_by_site('missing'), 0)
        self.assertEqual(self.db.query('SELECT COUNT(*) AS total FROM page_views')[0]['total'], 9)
        for query in (visits.totals_by_site, visits.totals_by_page, visits.totals_by_location,
                      visits.totals_by_coordinates, visits.totals_by_language, visits.totals_by_referrer):
            self.assertEqual(sum(row['page_views'] for row in query(exclude_bots=False)), 9)
            filtered = query(exclude_bots=True)
            self.assertEqual(len(filtered), 1)
            self.assertEqual(filtered[0]['page_views'], 2)
        self.assertEqual(visits.totals_by_site(exclude_bots=True)[0]['last_visited'],
                         visit.received_at.replace(tzinfo=None))
        self.assertEqual(visits.totals_by_page(exclude_bots=True)[0]['last_visited'],
                         visit.received_at.replace(tzinfo=None))
        self.assertEqual(len(visits.recent_visits(exclude_bots=True)), 2)
        days = ReportOptions(date(2026, 9, 27), date(2026, 9, 28), 'UTC').day_ranges()
        self.assertEqual(visits.daily_totals(days, exclude_bots=True), [
            dict(day='2026-09-27', page_views=2), dict(day='2026-09-28', page_views=0),
        ])
        all_sites = {row['site']: row for row in visits.totals_by_site()}
        self.assertEqual(all_sites['example']['known_bot_views'], 6)
        self.assertEqual(visits.totals_by_site(exclude_bots=True)[0]['known_bot_views'], 0)

    def test_explicit_tests_are_excluded_from_every_report_with_either_bot_setting(self):
        visits = VisitDb(self.db)
        visit = Visit(site='example', url='https://example.com/',
                      received_at=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
                      is_bot=False, browser_family='Chrome', visitor_id=uuid4().bytes,
                      country_code='CA', country_name='Canada', city_name='Hamilton',
                      latitude=43.2, longitude=-79.8, referrer_host='example.org', languages=('en-CA',))
        human_id = visits.record(visit)
        bot_id = visits.record(replace(visit, browser_family='Bytespider', visitor_id=uuid4().bytes))
        for site, url, timestamp in [
            ('mycount_smoke_1234', 'https://example.com/', datetime(2026, 9, 26, 12, tzinfo=timezone.utc)),
            ('example', 'https://example.com/__mycount_test__/1234', datetime(2026, 9, 28, 12, tzinfo=timezone.utc)),
            ('example', 'http://example.com:8080/__mycount_test__', datetime(2026, 9, 28, 13, tzinfo=timezone.utc)),
        ]:
            visits.record(replace(visit, site=site, url=url, received_at=timestamp,
                                 visitor_id=uuid4().bytes, country_code='US', country_name='United States',
                                 city_name='Test City', latitude=40.0, longitude=-100.0,
                                 referrer_host='test.example', languages=('fr',)))
        days = ReportOptions(date(2026, 9, 26), date(2026, 9, 29), 'UTC').day_ranges()
        for exclude_bots, expected in [(False, 2), (True, 1)]:
            with self.subTest(exclude_bots=exclude_bots):
                filters = dict(exclude_bots=exclude_bots, start=days[0][1], end=days[-1][2])
                for query in (visits.totals_by_site, visits.totals_by_page, visits.totals_by_location,
                              visits.totals_by_coordinates, visits.totals_by_language, visits.totals_by_referrer):
                    rows = query(**filters)
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]['page_views'], expected)
                site = visits.totals_by_site(**filters)[0]
                self.assertEqual(site['unique_browsers'], expected)
                self.assertEqual(site['last_visited'], visit.received_at.replace(tzinfo=None))
                recent = visits.recent_visits(**filters)
                self.assertEqual([row['page_view_id'] for row in recent],
                                 [human_id] if exclude_bots else [bot_id, human_id])
                self.assertEqual(visits.recent_visits(
                    **filters, before=(visit.received_at.replace(tzinfo=None), human_id)), [])
                self.assertEqual(visits.daily_totals(days, exclude_bots=exclude_bots), [
                    dict(day='2026-09-26', page_views=0), dict(day='2026-09-27', page_views=expected),
                    dict(day='2026-09-28', page_views=0), dict(day='2026-09-29', page_views=0),
                ])
        self.assertEqual(visits.count_by_site('example'), 1)
        self.assertEqual(visits.count_by_site('mycount_smoke_1234'), 0)
        self.assertEqual(visits.first_visit_at(), visit.received_at.replace(tzinfo=None))
        self.assertEqual(self.db.query('SELECT COUNT(*) AS n FROM page_views')[0]['n'], 5)

    def test_test_traffic_matching_keeps_similarly_named_real_sites_and_paths(self):
        visits = VisitDb(self.db)
        timestamp = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
        for site, url in [
            ('mycountXsmokeX1234', 'https://example.com/'),
            ('mycount_smoke', 'https://example.com/'),
            ('example', 'https://example.com/__mycount_test__article/'),
            ('example', 'https://example.com/docs/__mycount_test__/'),
            ('example', 'https://__mycount_test__.example.com/'),
        ]:
            visits.record(Visit(site=site, url=url, received_at=timestamp))
        self.assertEqual(sum(row['page_views'] for row in visits.totals_by_site()), 5)

    def test_first_visit_uses_earliest_timestamp_across_sites_including_bots(self):
        visits = VisitDb(self.db)
        self.assertIsNone(visits.first_visit_at())
        visit = Visit(site='first', url='https://example.com/',
                      received_at=datetime(2026, 9, 28, 12, tzinfo=timezone.utc))
        visits.record(visit)
        earliest = datetime(2026, 9, 23, 1, tzinfo=timezone.utc)
        visits.record(replace(visit, site='second', is_bot=True, received_at=earliest))
        visits.record(replace(visit, received_at=datetime(2026, 9, 25, tzinfo=timezone.utc)))
        self.assertEqual(visits.first_visit_at(), earliest.replace(tzinfo=None))

    def test_referrer_totals_group_hosts_include_unknowns_and_filter_bots(self):
        visits = VisitDb(self.db)
        self.assertEqual(visits.totals_by_referrer(), [])
        visit = Visit(site='first', url='https://example.com/',
                      received_at=datetime.now(timezone.utc))
        visits.record(replace(visit, referrer_host='search.example', referrer='https://search.example/a'))
        visits.record(replace(visit, site='second', referrer_host='search.example', referrer='https://search.example/b'))
        visits.record(replace(visit, referrer_host='another.example'))
        visits.record(visit)
        visits.record(replace(visit, referrer_host=''))
        visits.record(replace(visit, referrer_host='bot.example', is_bot=True))
        visits.record(replace(visit, referrer_host='bot.example', browser_family='GoogleOther'))
        visits.record(replace(visit, referrer_host='bot.example', browser_family='Googlebot'))
        self.assertEqual(visits.totals_by_referrer(exclude_bots=True), [
            {'referrer_host': None, 'page_views': 2},
            {'referrer_host': 'search.example', 'page_views': 2},
            {'referrer_host': 'another.example', 'page_views': 1},
        ])
        unfiltered = visits.totals_by_referrer()
        self.assertEqual(unfiltered[0], {'referrer_host': 'bot.example', 'page_views': 3})
        self.assertEqual(sum(row['page_views'] for row in unfiltered), 8)

    def test_recent_visits_include_all_matches_and_break_timestamp_ties(self):
        visits = VisitDb(self.db)
        self.assertEqual(visits.recent_visits(), [])
        timestamp = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
        visit = Visit(site='example', url='https://example.com/', received_at=timestamp)
        for index in range(25):
            visits.record(replace(visit, url=f'https://example.com/{index}'))
        visits.record(replace(visit, url='https://example.com/bot', is_bot=True,
                             received_at=datetime(2026, 9, 28, tzinfo=timezone.utc)))
        visits.record(replace(visit, url='https://example.com/google-other', browser_family='GoogleOther'))
        filtered = visits.recent_visits(exclude_bots=True)
        self.assertEqual([row['url'] for row in filtered],
                         [f'https://example.com/{index}' for index in range(24, -1, -1)])
        self.assertEqual(filtered[0]['received_at'], timestamp.replace(tzinfo=None))
        all_visits = visits.recent_visits()
        self.assertEqual(len(all_visits), 27)
        self.assertEqual(all_visits[0]['url'], 'https://example.com/bot')
        self.assertEqual(all_visits[1]['url'], 'https://example.com/google-other')
        self.assertEqual([row['url'] for row in all_visits[2:]],
                         [f'https://example.com/{index}' for index in range(24, -1, -1)])

    def test_location_totals_include_unknowns_and_combine_sites(self):
        visits = VisitDb(self.db)
        self.assertEqual(visits.totals_by_location(), [])
        visit = Visit(site='first', url='https://example.com/',
                      received_at=datetime.now(timezone.utc), country_name='Canada',
                      country_code='CA', region_name='Ontario', city_name='Hamilton')
        visits.record(visit)
        visits.record(replace(visit, site='second'))
        visits.record(replace(visit, country_name=None, country_code=None, region_name=None, city_name=None))
        visits.record(replace(visit, country_name='', country_code='', region_name='', city_name=''))
        visits.record(replace(visit, city_name='Toronto'))
        visits.record(replace(visit, region_name='Alberta'))
        visits.record(replace(visit, city_name=None))
        self.assertEqual(visits.totals_by_location(), [
            dict(country_name=None, country_code=None, region_name=None, city_name=None, page_views=2),
            dict(country_name='Canada', country_code='CA', region_name='Ontario', city_name='Hamilton', page_views=2),
            dict(country_name='Canada', country_code='CA', region_name='Alberta', city_name='Hamilton', page_views=1),
            dict(country_name='Canada', country_code='CA', region_name='Ontario', city_name=None, page_views=1),
            dict(country_name='Canada', country_code='CA', region_name='Ontario', city_name='Toronto', page_views=1),
        ])

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
        self.assertLess(abs((datetime.now(timezone.utc).replace(tzinfo=None) - row["received_at"]).total_seconds()), 5)
        self.assertEqual(self.db.query("SELECT language_tag FROM page_view_languages"), [{"language_tag": "en-CA"}])

    def test_region_code_removal_preserves_visits_and_region_names(self):
        self.assertEqual(self.db.query("SHOW COLUMNS FROM page_views LIKE 'region_code'"), [])
        self.db.execute('ALTER TABLE page_views ADD COLUMN region_code VARCHAR(32) NULL')
        view_id = VisitDb(self.db).record(Visit(
            site='mycount', url='https://example.com/',
            received_at=datetime.now(timezone.utc), region_name='Ontario',
            languages=('en-CA',),
        ))
        VisitorSchema(self.db).apply()
        VisitorSchema(self.db).apply()
        self.assertEqual(self.db.query("SHOW COLUMNS FROM page_views LIKE 'region_code'"), [])
        row = self.db.query('SELECT region_name FROM page_views WHERE page_view_id=%s', (view_id,))[0]
        self.assertEqual(row['region_name'], 'Ontario')
        self.assertEqual(self.db.query('SELECT language_tag FROM page_view_languages'),
                         [{'language_tag': 'en-CA'}])

    def test_ip_address_migration_and_both_address_families(self):
        self.db.execute('ALTER TABLE page_views DROP COLUMN ip_address')
        old_id = self.view(self.page())
        VisitorSchema(self.db).apply()
        self.assertIsNone(self.db.query(
            'SELECT ip_address FROM page_views WHERE page_view_id=%s', (old_id,)
        )[0]['ip_address'])
        visits = VisitDb(self.db)
        for address in ('8.8.8.8', '2001:4860:4860::8888', '::ffff:192.0.2.1'):
            view_id = visits.record(Visit(
                site='mycount', url='https://example.com/',
                received_at=datetime.now(timezone.utc), ip_address=address,
            ))
            VisitorSchema(self.db).apply()
            self.assertEqual(self.db.query(
                'SELECT ip_address FROM page_views WHERE page_view_id=%s', (view_id,)
            )[0]['ip_address'], address)

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

    def test_language_totals_use_first_preference_and_include_missing_with_filters(self):
        visits = VisitDb(self.db)
        self.assertEqual(visits.totals_by_language(), [])
        visit = Visit(site='language-test', url='https://example.com/',
                      received_at=datetime(2026, 9, 27, 12, tzinfo=timezone.utc),
                      languages=('en-CA', 'fr'))
        visits.record(visit)
        visits.record(replace(visit, languages=('fr', 'en-CA')))
        visits.record(replace(visit, languages=()))
        visits.record(replace(visit, languages=('en-CA',), is_bot=True))
        visits.record(replace(visit, received_at=datetime(2026, 9, 26, tzinfo=timezone.utc)))
        filters = dict(start=datetime(2026, 9, 27), end=datetime(2026, 9, 28))
        self.assertEqual(visits.totals_by_language(exclude_bots=True, **filters), [
            dict(language_tag=None, page_views=1), dict(language_tag='en-CA', page_views=1),
            dict(language_tag='fr', page_views=1),
        ])
        self.assertEqual(visits.totals_by_language(**filters), [
            dict(language_tag='en-CA', page_views=2), dict(language_tag=None, page_views=1),
            dict(language_tag='fr', page_views=1),
        ])

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

    def test_read_only_transaction_rejects_writes_and_recovers(self):
        with self.assertRaises(pymysql.OperationalError):
            with self.db.transaction(read_only=True):
                self.page()
        with self.db.transaction():
            self.page()
        self.assertEqual(self.db.query("SELECT COUNT(*) AS n FROM pages")[0]["n"], 1)
