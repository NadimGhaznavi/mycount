from datetime import datetime, timezone
import unittest

from mycount.activity.BrowserMetadata import BrowserMetadata
from mycount.entity.Visit import Visit


class BrowserMetadataTests(unittest.TestCase):
    def test_mobile_versions_and_device_preserve_city_and_referrer(self):
        visit = Visit(site='r3el', url='https://r3el.osoyalce.com/',
                      received_at=datetime.now(timezone.utc), city_name='Hamilton',
                      referrer_host='example.com')
        agent = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) '
                 'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 '
                 'Mobile/15E148 Safari/604.1')
        enriched = BrowserMetadata().enrich(visit, agent)
        self.assertEqual(enriched.browser_version, '17.4')
        self.assertEqual(enriched.os_version, '17.4')
        self.assertEqual(enriched.device_category, 'mobile')
        self.assertEqual(enriched.device_brand, 'Apple')
        self.assertEqual(enriched.device_model, 'iPhone')
        self.assertFalse(enriched.is_bot)
        self.assertEqual(enriched.city_name, 'Hamilton')
        self.assertEqual(enriched.referrer_host, 'example.com')

    def test_bot_classification(self):
        visit = Visit(site='r3el', url='https://r3el.osoyalce.com/',
                      received_at=datetime.now(timezone.utc))
        enriched = BrowserMetadata().enrich(visit, 'Googlebot/2.1 (+http://www.google.com/bot.html)')
        self.assertTrue(enriched.is_bot)
        self.assertIsNone(BrowserMetadata().enrich(visit, '').is_bot)

    def test_googleother_is_a_bot(self):
        visit = Visit(site='example', url='https://example.com/',
                      received_at=datetime.now(timezone.utc))
        agent = ('Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) '
                 'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.8010.52 '
                 'Mobile Safari/537.36 (compatible; GoogleOther)')
        self.assertTrue(BrowserMetadata().enrich(visit, agent).is_bot)
