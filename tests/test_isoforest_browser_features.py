"""Browser evidence must distinguish singleton networks without counting repeat hits."""

from dataclasses import replace
from datetime import datetime, timedelta
import math
import unittest

import numpy as np

from mycount.activity.BuildIsoForestFeatures import BuildIsoForestFeatures
from mycount.constants.DIsoForest import DIsoForest
from mycount.entity.IsoForestVisit import IsoForestVisit


def browser_visit(identifier=1, *, address='10.1.1.1', stamp=datetime(2026, 11, 13, 12),
                  site='blog', geoip='America/New_York', browser='America/New_York', **details):
    metadata = dict(screen_width=1920, screen_height=1080, available_width=1920,
                    available_height=1032, color_depth=24, pixel_depth=24, pixel_ratio=1.,
                    hardware_concurrency=8, device_memory=8., platform='Win32',
                    vendor='Google Inc.', max_touch_points=0, connection_effective_type='3g',
                    viewport_width=1800, viewport_height=800, timezone=browser)
    metadata.update(details)
    return IsoForestVisit(identifier, stamp, site, f'https://{site}.example/{identifier}',
                          address, 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/154.0.0.0',
                          tuple(metadata.items()), geoip, 'Windows', 'en-US', None)


def measurements(rows):
    observations = BuildIsoForestFeatures().build(rows)
    return {identifier: dict(zip(DIsoForest.FEATURES, observation.features))
            for observation in observations for identifier in observation.page_view_ids}


class IsoForestBrowserFeatureTests(unittest.TestCase):
    def test_shared_template_links_singleton_networks_across_midnight_despite_jitter(self):
        zones = [('America/El_Salvador', 'Asia/Singapore'),
                 ('America/Sao_Paulo', 'Europe/Helsinki'), ('Europe/Berlin', 'Asia/Jakarta'),
                 ('America/Mexico_City', 'Africa/Lagos'), (None, 'Asia/Seoul'),
                 ('America/New_York', 'Asia/Bangkok'), ('Asia/Manila', 'Asia/Jakarta')]
        start = datetime(2026, 11, 13, 13)
        rows = [browser_visit(i, address=f'10.{i}.1.1', stamp=start + timedelta(hours=2*i),
                              geoip=geoip, browser=browser, viewport_width=1700+i,
                              viewport_height=800+i)
                for i, (geoip, browser) in enumerate(zones, start=1)]
        values = measurements(rows)
        self.assertEqual(values, measurements(list(reversed(rows))))
        self.assertEqual(len(BuildIsoForestFeatures().build(rows)), 7)
        self.assertAlmostEqual(values[7]['template_ips_log'], math.log1p(7))
        self.assertAlmostEqual(values[7]['template_networks_log'], math.log1p(7))
        self.assertAlmostEqual(values[7]['template_timezones_log'], math.log1p(5))
        self.assertAlmostEqual(values[7]['template_viewports_log'], math.log1p(7))
        self.assertEqual(values[7]['timezone_gap_hours'], 1)
        self.assertEqual(values[6]['timezone_gap_hours'], 12)
        self.assertEqual(values[5]['timezone_coverage'], 0)
        self.assertEqual(values[5]['timezone_mismatch_share'], 0)
        self.assertNotEqual(values[1], values[7])
        # The original network representation could not distinguish these records.
        self.assertEqual({tuple(values[i][name] for name in DIsoForest.NETWORK_FEATURES)
                          for i in values}, {tuple(values[1][name] for name in DIsoForest.NETWORK_FEATURES)})

    def test_template_context_expires_at_rolling_boundary_and_does_not_use_future_visits(self):
        first = browser_visit()
        second = browser_visit(2, address='10.2.1.1', stamp=first.received_at + timedelta(hours=24))
        third = browser_visit(3, address='10.3.1.1', stamp=second.received_at + timedelta(seconds=1))
        values = measurements([third, first, second])
        self.assertAlmostEqual(values[1]['template_ips_log'], math.log1p(1))
        self.assertAlmostEqual(values[2]['template_ips_log'], math.log1p(2))
        self.assertAlmostEqual(values[3]['template_ips_log'], math.log1p(2))
        self.assertEqual(values[1], measurements([first])[1])

    def test_repeat_hits_use_one_latest_viewport_per_ip_and_expire_old_representatives(self):
        first = browser_visit()
        repeated = [browser_visit(i, stamp=first.received_at + timedelta(minutes=i),
                                  browser='Asia/Tokyo', viewport_width=1600+i)
                    for i in range(2, 12)]
        last = browser_visit(12, address='10.2.1.1',
                             stamp=first.received_at + timedelta(minutes=15))
        values = measurements([first, *repeated, last])[12]
        self.assertAlmostEqual(values['template_ips_log'], math.log1p(2))
        self.assertAlmostEqual(values['template_viewports_log'], math.log1p(2))
        self.assertAlmostEqual(values['template_timezones_log'], math.log1p(2))
        # Expiring a superseded hit must not remove its IP's newer observation.
        later = browser_visit(13, address='10.3.1.1',
                              stamp=first.received_at + timedelta(hours=24, minutes=5))
        self.assertAlmostEqual(measurements([first, *repeated, last, later])[13]['template_ips_log'],
                               math.log1p(3))

    def test_site_language_and_stable_device_fields_separate_templates(self):
        first = browser_visit()
        variants = [browser_visit(2, address='10.2.1.1', site='other'),
                    replace(browser_visit(3, address='10.3.1.1'), primary_language='fr'),
                    browser_visit(4, address='10.4.1.1', available_height=1040),
                    browser_visit(5, address='10.5.1.1', connection_effective_type='4g'),
                    replace(browser_visit(6, address='10.6.1.1'), user_agent='Different browser')]
        self.assertTrue(all(math.isclose(value['template_ips_log'], math.log1p(1))
                            for value in measurements([first, *variants]).values()))

    def test_timezone_offsets_respect_aliases_dst_and_missing_or_invalid_names(self):
        winter = browser_visit(browser='America/Bogota', geoip='America/New_York',
                               stamp=datetime(2026, 1, 1))
        before = browser_visit(2, address='10.2.1.1', browser='America/Bogota',
                               stamp=datetime(2026, 11, 1, 5, 30))
        after = browser_visit(3, address='10.3.1.1', browser='America/Bogota',
                              stamp=datetime(2026, 11, 1, 6, 30))
        values = measurements([winter, before, after])
        self.assertEqual(values[1]['timezone_coverage'], 1)
        self.assertEqual(values[1]['timezone_gap_hours'], 0)
        self.assertEqual(values[2]['timezone_gap_hours'], 1)
        self.assertEqual(values[3]['timezone_gap_hours'], 0)
        alias = measurements([browser_visit(browser='Etc/UTC', geoip='UTC')])[1]
        self.assertEqual(alias['timezone_coverage'], 1)
        self.assertEqual(alias['timezone_mismatch_share'], 0)
        for zone in (None, '', 'Unknown/Zone', '/etc/passwd', '../UTC'):
            with self.subTest(zone=zone):
                value = measurements([browser_visit(browser=zone)])[1]
                self.assertEqual(value['timezone_coverage'], 0)
                self.assertEqual(value['timezone_gap_hours'], 0)
                self.assertTrue(np.isfinite(list(value.values())).all())

    def test_platform_consistency_and_referrer_are_measurements_not_bot_decisions(self):
        cases = [('Windows', 'Win32', 1, 0), ('Windows', 'Linux x86_64', 1, 1),
                 ('Android', 'Linux x86_64', 1, 1), ('Android', 'Linux armv8l', 1, 0),
                 ('iOS', 'MacIntel', 1, 0), ('Mac OS X', 'MacIntel', 1, 0),
                 (None, 'Win32', 0, 0), ('Windows', None, 0, 0)]
        for os_family, platform, coverage, mismatch in cases:
            with self.subTest(os=os_family, platform=platform):
                row = replace(browser_visit(platform=platform), os_family=os_family,
                              referrer_host='www.google.com')
                value = measurements([row])[1]
                self.assertEqual(value['platform_os_coverage'], coverage)
                self.assertEqual(value['platform_os_mismatch_share'], mismatch)
                self.assertEqual(value['direct_referrer_share'], 0)
        self.assertEqual(measurements([browser_visit()])[1]['direct_referrer_share'], 1)

    def test_each_ip_has_equal_weight_even_when_one_browser_generates_many_visits(self):
        first = browser_visit(browser='Asia/Bangkok')
        rows = [replace(first, page_view_id=i) for i in range(1, 101)]
        rows.append(browser_visit(101, address='10.1.2.1'))
        value = measurements(rows)[1]
        self.assertEqual(value['timezone_coverage'], 1)
        self.assertEqual(value['timezone_mismatch_share'], .5)
        self.assertEqual(value['timezone_gap_hours'], 6)

    def test_missing_identity_or_device_metadata_does_not_form_a_shared_template(self):
        for row in (browser_visit(address=None), browser_visit(screen_width=None),
                    replace(browser_visit(), user_agent=None)):
            with self.subTest(row=row):
                value = measurements([row])[1]
                self.assertEqual(value['template_coverage'], 0)
                self.assertEqual(value['template_ips_log'], 0)
                self.assertTrue(np.isfinite(list(value.values())).all())

    def test_ipv6_templates_count_networks_using_the_configured_prefix(self):
        rows = [browser_visit(1, address='2001:db8:1:1::1'),
                browser_visit(2, address='2001:db8:1:2::1'),
                browser_visit(3, address='2001:db8:2::1')]
        value = measurements(rows)[3]
        self.assertAlmostEqual(value['template_ips_log'], math.log1p(3))
        self.assertAlmostEqual(value['template_networks_log'], math.log1p(2))


if __name__ == '__main__':
    unittest.main()
