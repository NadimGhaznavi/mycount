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
