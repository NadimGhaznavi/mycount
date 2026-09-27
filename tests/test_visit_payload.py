import unittest

from mycount.interface.VisitPayload import InvalidVisit, VisitPayload


class VisitPayloadTests(unittest.TestCase):
    def setUp(self):
        self.origin = 'https://ax3l.osoyalce.com'
        self.payload = {
            'schema_version': 1, 'event': 'page_view', 'site': 'ax3l',
            'url': self.origin + '/page?private=value#fragment',
            'languages': ['en'], 'user_agent': 'Example',
        }

    def test_preserves_site_and_strips_query_and_fragment(self):
        visit, agent = VisitPayload().resolve(self.payload, self.origin)
        self.assertEqual(visit.site, 'ax3l')
        self.assertEqual(visit.url, self.origin + '/page')
        self.assertEqual(agent, 'Example')

    def test_rejects_invalid_site_labels(self):
        for site in ('', 'a' * 101, 'site with spaces', [], None, '\ud800'):
            with self.subTest(site=site), self.assertRaises(InvalidVisit):
                VisitPayload().resolve({**self.payload, 'site': site}, self.origin)

    def test_rejects_other_hosts_schemes_ports_and_credentials(self):
        for url in ('https://mycount.osoyalce.com/', 'http://ax3l.osoyalce.com/',
                    'https://ax3l.osoyalce.com:444/', 'https://user@ax3l.osoyalce.com/'):
            with self.subTest(url=url), self.assertRaises(InvalidVisit):
                VisitPayload().resolve({**self.payload, 'url': url}, self.origin)

    def test_optional_details_and_referrer_are_normalized_without_mutating_input(self):
        details = {'timezone': 'America/Toronto', 'viewport_width': 1920,
                   'device_memory': 0.5, 'webdriver': False, 'hardware_concurrency': None}
        payload = {**self.payload, 'referrer': 'https://WWW.Example.com/path?secret=yes#fragment',
                   'client_details': details}
        visit, agent = VisitPayload().resolve(payload, self.origin)
        self.assertEqual(visit.referrer_host, 'www.example.com')
        self.assertEqual(visit.user_agent, agent)
        self.assertEqual(dict(visit.client_details), {
            'timezone': 'America/Toronto', 'viewport_width': 1920,
            'device_memory': 0.5, 'webdriver': False,
        })
        self.assertIn('hardware_concurrency', details)
        details['timezone'] = 'changed'
        self.assertEqual(dict(visit.client_details)['timezone'], 'America/Toronto')

    def test_legacy_payload_has_unknown_optional_details(self):
        visit, _ = VisitPayload().resolve(self.payload, self.origin)
        self.assertIsNone(visit.referrer_host)
        self.assertEqual(visit.client_details, ())

    def test_empty_idn_and_ipv6_referrers(self):
        for referrer, host in ((None, None), ('', None),
                               ('https://bücher.example/page', 'xn--bcher-kva.example'),
                               ('http://[2001:db8::1]:8080/path', '2001:db8::1')):
            with self.subTest(referrer=referrer):
                visit, _ = VisitPayload().resolve({**self.payload, 'referrer': referrer}, self.origin)
                self.assertEqual(visit.referrer_host, host)

    def test_rejects_invalid_referrers(self):
        for referrer in ([], 1, 'javascript:alert(1)', 'https://user:secret@example.com',
                         'https://example.com:bad', 'https://exa mple.com', '//example.com',
                         'https://example.com/\nsecret', 'https://example.com/\ud800',
                         'https://example.com/' + 'x' * 4096):
            with self.subTest(referrer=referrer), self.assertRaises(InvalidVisit):
                VisitPayload().resolve({**self.payload, 'referrer': referrer}, self.origin)

    def test_rejects_invalid_optional_details(self):
        for details in (None, [], {'unexpected': None}, {'screen_width': True},
                        {'screen_width': -1}, {'screen_width': 1.5},
                        {'device_memory': float('nan')}, {'pixel_ratio': float('inf')},
                        {'cookie_enabled': 'true'}, {'timezone': '\ud800'},
                        {'timezone': 'x' * 129}, {'platform': 'bad\nvalue'},
                        {'navigation_type': 'unknown'}, {'timezone_offset': 1441},
                        {'device_memory': {'nested': 1}}):
            with self.subTest(details=details), self.assertRaises(InvalidVisit):
                VisitPayload().resolve({**self.payload, 'client_details': details}, self.origin)

    def test_still_rejects_unknown_and_missing_top_level_fields(self):
        with self.assertRaises(InvalidVisit):
            VisitPayload().resolve({**self.payload, 'cookies': 'secret'}, self.origin)
        del self.payload['languages']
        with self.assertRaises(InvalidVisit):
            VisitPayload().resolve(self.payload, self.origin)
