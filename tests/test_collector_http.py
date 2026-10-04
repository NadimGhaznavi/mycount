import unittest
from unittest.mock import Mock, patch
from uuid import UUID

from werkzeug.test import Client

from mycount.constants.DCaddy import DCaddy
from mycount.constants.DMyCount import DMyCount
from mycount.interface.GeoIpUnavailable import GeoIpUnavailable
from mycount.interface.CollectorHttp import CollectorHttp
from mycount.interface.VisitPayload import VisitPayload
from mycount.activity.BrowserMetadata import BrowserMetadata
from mycount.activity.CollectVisit import CollectVisit
from mycount.entity.GeoLocation import GeoLocation


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

    def test_geolocation_failure_returns_503_with_cors(self):
        self.collector.record.side_effect = GeoIpUnavailable('private service details')
        with self.assertLogs(level='ERROR'):
            response = self.client.post('/count', json={}, headers={'Origin': DMyCount.ORIGINS[0]})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], DMyCount.ORIGINS[0])
        self.assertNotIn(b'private service details', response.data)

    def test_failed_geolocation_does_not_open_the_visitor_database(self):
        with patch('mycount.activity.CollectVisit.GeoIp') as geo, patch('mycount.activity.CollectVisit.DbMgr') as db:
            geo.return_value.locate.side_effect = GeoIpUnavailable('offline')
            origin = DMyCount.ORIGINS[0]
            with self.assertRaises(GeoIpUnavailable):
                CollectVisit(VisitPayload(), BrowserMetadata()).record({
                    'schema_version': 1, 'event': 'page_view', 'site': 'mycount',
                    'url': origin + '/', 'languages': [], 'user_agent': '',
                }, '8.8.8.8', origin)
            db.assert_not_called()

    def test_sites_pass_preflight_and_payload_validation(self):
        self.collector.record.side_effect = lambda payload, address, origin: VisitPayload().resolve(payload, origin)
        for site in ('mycount', 'ax3l', 'r3el', 'bmgeoip', 'bmdynip'):
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

    def test_extended_visit_keeps_city_and_referrer_through_collection(self):
        collector = CollectVisit(VisitPayload(), BrowserMetadata())
        client = Client(CollectorHttp(collector, DMyCount.ORIGINS))
        origin = 'https://r3el.osoyalce.com'
        payload = {
            'schema_version': 1, 'event': 'page_view', 'site': 'r3el',
            'url': origin + '/', 'languages': ['en-CA'], 'user_agent': 'Example',
            'referrer': 'https://search.example/?private=query',
            'search': '?campaign=example',
            'client_details': {'timezone': 'America/Toronto'},
            'visitor_id': '3e8073e0-5f15-4f14-bccc-b4b5cb47e330',
        }
        with patch('mycount.activity.CollectVisit.DbMgr') as database, \
                patch('mycount.activity.CollectVisit.GeoIp') as geo, \
                patch('mycount.activity.CollectVisit.VisitDb') as visits:
            geo.return_value.locate.return_value = GeoLocation(
                country_name='Canada', country_code='CA', region_name='Ontario', city_name='Hamilton',
                latitude=43.2557, longitude=-79.8711, zip='00123', timezone='America/New_York')
            response = client.post('/count', json=payload, headers={
                'Origin': origin, DCaddy.VISITOR_HEADER: '8.8.8.8',
            }, environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
            self.assertEqual(response.status_code, 204)
            self.assertEqual(response.headers['Access-Control-Allow-Origin'], origin)
            geo.return_value.locate.assert_called_once_with('8.8.8.8')
            saved = visits.return_value.record.call_args.args[0]
            self.assertEqual(saved.city_name, 'Hamilton')
            self.assertEqual(saved.region_name, 'Ontario')
            self.assertEqual(saved.country_code, 'CA')
            self.assertEqual(saved.referrer_host, 'search.example')
            self.assertEqual(saved.referrer, payload['referrer'])
            self.assertEqual(saved.search, payload['search'])
            self.assertEqual(saved.country_name, 'Canada')
            self.assertEqual(saved.latitude, 43.2557)
            self.assertEqual(saved.longitude, -79.8711)
            self.assertEqual(saved.zip, '00123')
            self.assertEqual(saved.timezone, 'America/New_York')
            self.assertEqual(dict(saved.client_details), {'timezone': 'America/Toronto'})
            self.assertEqual(saved.visitor_id, UUID(payload['visitor_id']).bytes)
            self.assertEqual(saved.ip_address, '8.8.8.8')
            database.return_value.close.assert_called_once()

            # Malformed optional data is rejected before opening another DB connection.
            payload['client_details']['screen_width'] = True
            response = client.post('/count', json=payload, headers={'Origin': origin})
            self.assertEqual(response.status_code, 400)
            database.assert_called_once()

    @patch('mycount.activity.CountVisits.DbMgr')
    def test_read_only_site_counter(self, factory):
        factory.return_value.query.return_value = [{'visits': 42}]
        origin = DMyCount.ORIGINS[0]
        response = self.client.get('/get_count?site=r3el', headers={'Origin': origin})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'site': 'r3el', 'visits': 42})
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], origin)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        factory.return_value.close.assert_called_once()
        factory.return_value.insert.assert_not_called()
        factory.return_value.execute.assert_not_called()
        self.collector.record.assert_not_called()
        factory.reset_mock()
        for query in ('', '?site=', '?site=a&site=b', '?site=bad%20site', '?site=' + 'a'*101):
            self.assertEqual(self.client.get('/get_count' + query, headers={'Origin': origin}).status_code, 400)
        self.assertEqual(self.client.get('/get_count?site=r3el').status_code, 403)
        self.assertEqual(self.client.get('/get_count?site=r3el', headers={'Origin': 'https://bad.example'}).status_code, 403)
        self.assertEqual(self.client.post('/get_count?site=r3el', headers={'Origin': origin}).status_code, 405)
        factory.assert_not_called()
        import pymysql
        factory.return_value.query.side_effect = pymysql.OperationalError(2003, 'private details')
        with self.assertLogs(level='ERROR'):
            response = self.client.get('/get_count?site=r3el', headers={'Origin': origin})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'private details', response.data)
        factory.return_value.close.assert_called_once()
