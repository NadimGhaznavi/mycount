import unittest
from unittest.mock import Mock

from werkzeug.test import Client

from mycount.constants.DCaddy import DCaddy
from mycount.constants.DMyCount import DMyCount
from mycount.interface.CollectorHttp import CollectorHttp


class CollectorHttpTests(unittest.TestCase):
    def setUp(self):
        self.collector = Mock()
        self.client = Client(CollectorHttp(self.collector, DMyCount.ORIGIN))

    def test_count_preflight_and_post(self):
        response = self.client.options('/count', headers={
            'Origin': DMyCount.ORIGIN,
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type',
        })
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], DMyCount.ORIGIN)
        self.collector.record.assert_not_called()

        payload = {'event': 'page_view'}
        response = self.client.post('/count', json=payload, headers={
            'Origin': DMyCount.ORIGIN,
            DCaddy.VISITOR_HEADER: '8.8.8.8',
        }, environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(response.status_code, 204)
        self.collector.record.assert_called_once_with(payload, '8.8.8.8')

    def test_other_paths_do_not_collect(self):
        for path in ('/', '/count/', '/counter', '/count/other'):
            with self.subTest(path=path):
                response = self.client.post(path, json={}, headers={'Origin': DMyCount.ORIGIN})
                self.assertEqual(response.status_code, 404)
        self.collector.record.assert_not_called()

    def test_health(self):
        self.assertEqual(self.client.get('/health').status_code, 204)
        self.collector.record.assert_not_called()
