"""Campaign evidence must distinguish rotating crawls from ordinary short visits."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from mycount.activity.DetectCrawlCampaigns import DetectCrawlCampaigns
from mycount.entity.CampaignVisit import CampaignVisit
from mycount.entity.Visit import Visit


def campaign(*, count=12, site="example", minutes=None):
    visits = []
    for index in range(count):
        timestamp = datetime(2026, 10, 1) + timedelta(
            minutes=minutes[index] if minutes is not None else index * 22)
        home = CampaignVisit(index * 2 + 1, site, "https://example.com/", timestamp,
                             (index + 1).to_bytes(16), f"192.0.2.{index + 1}", None)
        visits.extend((home, replace(home, page_view_id=index * 2 + 2,
                                    url=f"https://example.com/article/{index}/",
                                    received_at=timestamp + timedelta(seconds=4),
                                    referrer_host="example.com")))
    return visits


class CrawlCampaignTests(unittest.TestCase):
    def test_rotating_page_sweep_and_input_order_independence(self):
        rows = campaign()
        expected = tuple(range(1, 25))
        self.assertEqual(DetectCrawlCampaigns.find(rows), expected)
        self.assertEqual(DetectCrawlCampaigns.find(list(reversed(rows))), expected)

    def test_small_samples_and_sweeps_outside_the_window_are_not_classified(self):
        self.assertEqual(DetectCrawlCampaigns.find(campaign(count=11)), ())
        self.assertEqual(DetectCrawlCampaigns.find(campaign(minutes=[n * 360 for n in range(12)])), ())

    def test_sites_and_origins_do_not_share_evidence(self):
        for field, value in (("site", "other"), ("url", "https://other.example/")):
            rows = campaign()
            for index in range(12):
                row = rows[index]
                change = value if field == "site" else row.url.replace("https://example.com/", value)
                rows[index] = replace(row, **{field: change})
            with self.subTest(field=field):
                self.assertEqual(DetectCrawlCampaigns.find(rows), ())

    def test_shared_networks_reused_identities_and_popular_pages_do_not_establish_crawls(self):
        cases = [
            [replace(row, ip_address="192.0.2.1") for row in campaign()],
            [replace(row, visitor_id=b"x" * 16) for row in campaign()],
            [replace(row, url="https://example.com/popular/")
             if row.page_view_id % 2 == 0 else row for row in campaign()],
        ]
        for rows in cases:
            with self.subTest(rows=rows[:2]):
                self.assertEqual(DetectCrawlCampaigns.find(rows), ())

    def test_normal_arrivals_and_reading_times_do_not_match(self):
        irregular = [0, 13, 51, 68, 121, 150, 197, 216, 281, 322, 341, 409]
        self.assertEqual(DetectCrawlCampaigns.find(campaign(minutes=irregular)), ())
        for seconds in (1, 9, 120):
            rows = [replace(row, received_at=row.received_at + timedelta(seconds=seconds - 4))
                    if row.page_view_id % 2 == 0 else row for row in campaign()]
            with self.subTest(seconds=seconds):
                self.assertEqual(DetectCrawlCampaigns.find(rows), ())

    def test_one_regular_run_cannot_classify_an_otherwise_irregular_crowd(self):
        minutes = [0, 13, 51, 68, 121, 143, 165, 187, 209, 231, 253, 275]
        self.assertEqual(DetectCrawlCampaigns.find(campaign(minutes=minutes)), ())

    def test_missing_ticks_and_small_timing_jitter_are_supported(self):
        minutes = [0, 22, 44, 88, 110, 176, 198, 220, 242, 286, 308, 330]
        rows = campaign(minutes=minutes)
        rows = [replace(row, received_at=row.received_at + timedelta(
            seconds=20 if (row.page_view_id - 1) // 2 % 2 else 0)) for row in rows]
        self.assertEqual(DetectCrawlCampaigns.find(rows), tuple(range(1, 25)))

    def test_readers_with_longer_sessions_and_external_referrals_are_preserved(self):
        rows = campaign()
        human = replace(rows[0], page_view_id=100, visitor_id=b"h" * 16,
                        ip_address="198.51.100.1", received_at=rows[0].received_at + timedelta(minutes=1))
        reader = replace(human, page_view_id=101, url="https://example.com/reading/",
                         received_at=human.received_at + timedelta(minutes=3))
        search = replace(human, page_view_id=102, visitor_id=b"s" * 16,
                         ip_address="198.51.100.2", url="https://example.com/search-result/",
                         referrer_host="search.example")
        self.assertEqual(DetectCrawlCampaigns.find(rows + [human, reader, search]), tuple(range(1, 25)))

    def test_a_browser_profile_alone_does_not_flag_a_visit(self):
        visit = Visit(site="example", url="https://example.com/",
                      received_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                      browser_family="Chrome", os_family="Windows",
                      client_details=(("platform", "Win32"), ("vendor", "Google Inc.")))
        self.assertTrue(DetectCrawlCampaigns.is_candidate(visit))
        self.assertFalse(DetectCrawlCampaigns.is_candidate(replace(visit, client_details=())))
        self.assertFalse(DetectCrawlCampaigns.is_candidate(replace(visit, os_family="Linux")))
        row = campaign()[0]
        self.assertEqual(DetectCrawlCampaigns.find([row]), ())
