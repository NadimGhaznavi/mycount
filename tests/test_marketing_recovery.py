"""Uncertain commits, repeat submissions, and conservative file reconciliation."""

from datetime import datetime, timezone
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import Mock

import pymysql

from mycount.activity.ReconcileMarketingScreenshots import ReconcileMarketingScreenshots
from mycount.activity.SaveMarketingPost import SaveMarketingPost
from mycount.entity.MarketingPost import MarketingPost
from mycount.interface.DbCommitUncertain import DbCommitUncertain
from mycount.interface.MarketingScreenshots import MarketingScreenshots


class MarketingRecoveryTests(unittest.TestCase):
    def test_lost_commit_reply_preserves_image_and_retry_confirms_same_post(self):
        post = MarketingPost(datetime.now(timezone.utc), 'X', 'https://example.com/', '')
        committed = []
        posts = Mock()
        posts.submission.side_effect = [None, 42]

        def commit_then_lose_reply(value):
            committed.append(value)
            raise DbCommitUncertain(2013, 'Lost commit reply')

        posts.record.side_effect = commit_then_lose_reply
        with TemporaryDirectory() as directory:
            files = MarketingScreenshots(Path(directory))
            save = SaveMarketingPost(posts, files)
            with self.assertRaises(DbCommitUncertain):
                save.save(post, b'image')
            self.assertEqual(files.read(committed[0].screenshot_path), b'image')
            self.assertEqual(save.save(post, b'reselected image'), 42)
            posts.record.assert_called_once()
            self.assertEqual(len(list((Path(directory) / 'pages/marketing').iterdir())), 1)

    def test_reconciliation_keeps_referenced_and_recent_files(self):
        with TemporaryDirectory() as directory:
            files = MarketingScreenshots(Path(directory))
            kept, orphan, recent = (files.save(b'image') for _ in range(3))
            for reference in (kept, orphan):
                os.utime(Path(directory) / reference, (time.time() - 172800,) * 2)
            unrelated = Path(directory) / 'pages/marketing/manual.png'
            unrelated.write_bytes(b'manual')
            posts = Mock()
            posts.screenshot_referenced.side_effect = lambda reference: reference == kept
            self.assertEqual(ReconcileMarketingScreenshots(posts, files).run(), 1)
            self.assertEqual(files.read(kept), b'image')
            self.assertEqual(files.read(recent), b'image')
            self.assertTrue(unrelated.exists())
            self.assertFalse((Path(directory) / orphan).exists())
            self.assertEqual(posts.screenshot_referenced.call_count, 2)

    def test_reconciliation_does_not_delete_when_reference_query_fails(self):
        with TemporaryDirectory() as directory:
            files = MarketingScreenshots(Path(directory))
            reference = files.save(b'image')
            os.utime(Path(directory) / reference, (time.time() - 172800,) * 2)
            posts = Mock()
            posts.screenshot_referenced.side_effect = pymysql.OperationalError(2013, 'offline')
            with self.assertRaises(pymysql.OperationalError):
                ReconcileMarketingScreenshots(posts, files).run()
            self.assertEqual(files.read(reference), b'image')
