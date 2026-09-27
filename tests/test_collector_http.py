import unittest
from unittest.mock import Mock

from werkzeug.test import Client

from mycount.constants.DCaddy import DCaddy
from mycount.constants.DMyCount import DMyCount
from mycount.interface.CollectorHttp import CollectorHttp
from mycount.interface.VisitPayload import VisitPayload


class CollectorHttpTests(unittest.TestCase):
    def setUp(self):
        self.collector = Mock()
        self.client = Client(CollectorHttp(self.collector, DMyCount.ORIGINS))

    def test_count_preflight_and_post(self):
        response = self.client.options('/count', headers={
            'Origin': DMyCount.ORIGINS[0],
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type',
        })
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], DMyCount.ORIGINS[0])
        self.collector.record.assert_not_called()

        payload = {'event': 'page_view'}
        response = self.client.post('/count', json=payload, headers={
            'Origin': DMyCount.ORIGINS[0],
            DCaddy.VISITOR_HEADER: '8.8.8.8',
        }, environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(response.status_code, 204)
        self.collector.record.assert_called_once_with(payload, '8.8.8.8', DMyCount.ORIGINS[0])

    def test_other_paths_do_not_collect(self):
        for path in ('/', '/count/', '/counter', '/count/other'):
            with self.subTest(path=path):
                response = self.client.post(path, json={}, headers={'Origin': DMyCount.ORIGINS[0]})
                self.assertEqual(response.status_code, 404)
        self.collector.record.assert_not_called()

    def test_health(self):
        self.assertEqual(self.client.get('/health').status_code, 204)
        self.collector.record.assert_not_called()

    def test_sites_pass_preflight_and_payload_validation(self):
        self.collector.record.side_effect = lambda payload, address, origin: VisitPayload().resolve(payload, origin)
        for site in ('mycount', 'ax3l', 'r3el'):
            origin = f'https://{site}.osoyalce.com'
            with self.subTest(site=site):
                response = self.client.options('/count', headers={
                    'Origin': origin, 'Access-Control-Request-Method': 'POST',
                    'Access-Control-Request-Headers': 'Content-Type',
                })
                self.assertEqual(response.status_code, 204)
                self.assertEqual(response.headers['Access-Control-Allow-Origin'], origin)
                response = self.client.post('/count', json={
                    'schema_version': 1, 'event': 'page_view', 'site': site,
                    'url': origin + '/example', 'languages': ['en'], 'user_agent': '',
                }, headers={'Origin': origin}, environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
                self.assertEqual(response.status_code, 204)
                self.assertEqual(response.headers['Access-Control-Allow-Origin'], origin)

    def test_unlisted_missing_and_null_origins_are_rejected(self):
        for origin in ('https://unlisted.example', 'null', None):
            for method in ('POST', 'OPTIONS'):
                headers = {'Origin': origin} if origin else {}
                response = self.client.open('/count', method=method, json={}, headers=headers)
                self.assertEqual(response.status_code, 403)
                self.assertNotIn('Access-Control-Allow-Origin', response.headers)
        self.collector.record.assert_not_called()

    def test_page_url_must_match_request_origin(self):
        self.collector.record.side_effect = lambda payload, address, origin: VisitPayload().resolve(payload, origin)
        response = self.client.post('/count', json={
            'schema_version': 1, 'event': 'page_view', 'site': 'ax3l',
            'url': DMyCount.ORIGINS[1] + '/', 'languages': [], 'user_agent': '',
        }, headers={'Origin': DMyCount.ORIGINS[0]}, environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(response.status_code, 400)
