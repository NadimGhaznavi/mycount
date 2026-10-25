from datetime import datetime, timezone
import unittest

from mycount.activity.BrowserMetadata import BrowserMetadata
from mycount.entity.Visit import Visit
from browser_automation_cases import browser_automation_cases


class BrowserMetadataTests(unittest.TestCase):
    def test_automation_profiles_and_nearby_legitimate_browsers(self):
        for name, visit, agent, expected in browser_automation_cases():
            with self.subTest(profile=name):
                enriched = BrowserMetadata().enrich(visit, agent)
                self.assertEqual(enriched.is_bot, expected)
                self.assertEqual(enriched.client_details, visit.client_details)

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

    def test_bytespider_is_a_bot_even_when_parser_does_not_flag_it(self):
        visit = Visit(site='example', url='https://example.com/',
                      received_at=datetime.now(timezone.utc))
        agent = ('Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 '
                 '(KHTML, like Gecko) Mobile Safari/537.36 '
                 '(compatible; Bytespider; https://zhanzhang.toutiao.com/)')
        enriched = BrowserMetadata().enrich(visit, agent)
        self.assertEqual(enriched.browser_family, 'Bytespider')
        self.assertTrue(enriched.is_bot)

    def test_known_automation_user_agents_are_bots(self):
        visit = Visit(site='example', url='https://example.com/',
                      received_at=datetime.now(timezone.utc))
        agents = (
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) HeadlessChrome/155.0.0.0 Safari/537.36',
            'Mozilla/5.0 (compatible; Dataprovider.com)',
            'Mozilla/5.0 AppleWebKit/537.36 Chrome/120.0.0.0 '
            'Safari/537.36 web-image-collection-research',
            'Mozilla/5.0 (compatible; DATAPROVIDER.COM)',
        )
        for agent in agents:
            with self.subTest(agent=agent):
                self.assertTrue(BrowserMetadata().enrich(visit, agent).is_bot)

    def test_webdriver_is_a_bot_even_without_a_user_agent(self):
        visit = Visit(site='example', url='https://example.com/',
                      received_at=datetime.now(timezone.utc),
                      client_details=(('webdriver', True),))
        for agent in ('Mozilla/5.0 Chrome/155.0.0.0', ''):
            with self.subTest(agent=agent):
                self.assertTrue(BrowserMetadata().enrich(visit, agent).is_bot)

    def test_webdriver_false_and_missing_metadata_do_not_imply_a_bot(self):
        visit = Visit(site='example', url='https://example.com/',
                      received_at=datetime.now(timezone.utc),
                      client_details=(('webdriver', False),))
        self.assertFalse(BrowserMetadata().enrich(visit, 'Chrome/155.0.0.0').is_bot)
        self.assertIsNone(BrowserMetadata().enrich(visit, '').is_bot)
