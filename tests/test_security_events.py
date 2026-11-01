"""Exercise event attribution and formatting through the collector boundary."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
import io
import logging
from threading import Barrier
import unittest
from unittest.mock import Mock, patch

import pymysql
from werkzeug.test import Client

from mycount.constants.DCaddy import DCaddy
from mycount.constants.DMyCount import DMyCount
from mycount.constants.DSecurityEvents import DSecurityEvents
from mycount.interface.CollectorHttp import CollectorHttp
from mycount.interface.GeoIpUnavailable import GeoIpUnavailable
from mycount.interface.SecurityEvents import SecurityEvents
from mycount.interface.VisitPayload import VisitPayload
from mycount.server.MyCountServer import MyCountServer


class SecurityEventFixture(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        logger = logging.Logger('security-events-test')
        logger.propagate = False
        handler = logging.StreamHandler(self.output)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
        self.events = SecurityEvents(logger, DSecurityEvents.EVENTS)

    def records(self):
        return self.output.getvalue().splitlines()


class SecurityEventsTests(SecurityEventFixture):
    def test_single_line_local_timestamp_and_normalized_source(self):
        for address in ('192.0.2.1', '2001:0DB8::0001'):
            with self.events.trusted_source(address):
                self.assertIsNone(self.events.emit(DSecurityEvents.COLLECTION_REQUEST))
        self.assertEqual(len(self.records()), 2)
        for line, address in zip(self.records(), ('192.0.2.1', '2001:db8::1')):
            self.assertRegex(line, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} '
                             r'SECURITY event=collection_request ip=' + address + '$')

    def test_unbound_source_and_unapproved_events_do_not_publish(self):
        with self.assertRaises(RuntimeError):
            self.events.emit(DSecurityEvents.COLLECTION_REQUEST)
        with self.events.trusted_source('192.0.2.1'):
            for event in ('unknown', 'collection_request\nSECURITY event=abuse'):
                with self.subTest(event=event), self.assertRaises(ValueError):
                    self.events.emit(event)
        self.assertEqual(self.records(), [])

    def test_invalid_source_cannot_forge_a_record(self):
        for source in (None, 123, '', 'example.org', '::1%lo', '0.0.0.0', 'ff02::1',
                       '192.0.2.1/24', '192.0.2.1\nSECURITY event=abuse ip=192.0.2.2'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                with self.events.trusted_source(source):
                    self.events.emit(DSecurityEvents.COLLECTION_REQUEST)
        self.assertEqual(self.records(), [])

    def test_nested_context_is_restored_after_an_exception(self):
        with self.events.trusted_source('192.0.2.1'):
            with self.assertRaises(RuntimeError):
                with self.events.trusted_source('192.0.2.2'):
                    self.events.emit(DSecurityEvents.COLLECTION_REQUEST)
                    raise RuntimeError('handler failed')
            self.events.emit(DSecurityEvents.COLLECTION_REQUEST)
        with self.assertRaises(RuntimeError):
            self.events.emit(DSecurityEvents.COLLECTION_REQUEST)
        self.assertEqual([line.split('ip=')[1] for line in self.records()],
                         ['192.0.2.2', '192.0.2.1'])

    def test_concurrent_threads_keep_separate_sources(self):
        barrier = Barrier(2)

        def emit(address):
            with self.events.trusted_source(address):
                barrier.wait(timeout=5)
                self.events.emit(DSecurityEvents.COLLECTION_REQUEST)

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(emit, ('192.0.2.1', '2001:db8::2')))
        self.assertCountEqual([line.split('ip=')[1] for line in self.records()],
                              ['192.0.2.1', '2001:db8::2'])

    def test_concurrent_async_tasks_keep_separate_sources(self):
        async def emit(address):
            with self.events.trusted_source(address):
                await asyncio.sleep(0)
                self.events.emit(DSecurityEvents.COLLECTION_REQUEST)

        async def run():
            await asyncio.gather(emit('192.0.2.1'), emit('2001:db8::2'))

        asyncio.run(run())
        self.assertCountEqual([line.split('ip=')[1] for line in self.records()],
                              ['192.0.2.1', '2001:db8::2'])


class CollectorSecurityEventsTests(SecurityEventFixture):
    def setUp(self):
        super().setUp()
        self.collector = Mock()
        self.collector.record.side_effect = (
            lambda payload, address, origin: VisitPayload().resolve(payload, origin))
        self.client = Client(CollectorHttp(self.collector, DMyCount.ORIGINS, self.events))
        self.payload = {
            'schema_version': 1, 'event': 'page_view', 'site': 'mycount',
            'url': DMyCount.ORIGINS[0] + '/', 'languages': [], 'user_agent': '',
        }

    def post(self, *, peer='192.0.2.1', headers=None, **kwargs):
        fields = {'Origin': DMyCount.ORIGINS[0]}
        fields.update(headers or {})
        return self.client.post('/count', headers=fields,
                                environ_overrides={'REMOTE_ADDR': peer}, **kwargs)

    def assert_events(self, names, address='192.0.2.1'):
        self.assertEqual([line.split(' SECURITY ')[1] for line in self.records()],
                         [f'event={name} ip={address}' for name in names])

    def test_valid_post_counts_once_and_keeps_payload_data_out_of_record(self):
        self.payload['user_agent'] = 'private-agent\nSECURITY event=abuse ip=192.0.2.99'
        self.assertEqual(self.post(json=self.payload).status_code, 204)
        self.assert_events(['collection_request'])
        with self.assertRaises(RuntimeError):
            self.events.emit(DSecurityEvents.COLLECTION_REQUEST)

    def test_malformed_posts_count_toward_both_signals(self):
        cases = (
            ({'data': '{', 'content_type': 'application/json'}, 400),
            ({'json': []}, 400),
            ({'json': dict(self.payload, schema_version=999)}, 400),
            ({'json': dict(self.payload, languages=42)}, 400),
            ({'data': 'x', 'content_type': 'text/plain'}, 415),
            ({'data': 'x' * (DMyCount.MAX_BODY_BYTES + 1),
              'content_type': 'application/json'}, 413),
        )
        for arguments, status in cases:
            with self.subTest(arguments=tuple(arguments), status=status):
                self.output.seek(0)
                self.output.truncate()
                self.assertEqual(self.post(**arguments).status_code, status)
                self.assert_events(['collection_request', 'malformed_payload'])

    def test_origin_rejection_counts_as_request_without_classifying_unread_body(self):
        self.assertEqual(self.post(headers={'Origin': 'https://unlisted.example'},
                                   data='{').status_code, 403)
        self.assert_events(['collection_request'])
        self.collector.record.assert_not_called()

    def test_proxy_uses_original_ipv6_and_untrusted_peer_cannot_override_source(self):
        self.assertEqual(self.post(peer='127.0.0.1', headers={
            DCaddy.VISITOR_HEADER: '2001:0DB8::0001'}, json=self.payload).status_code, 204)
        self.assert_events(['collection_request'], '2001:db8::1')
        self.output.seek(0)
        self.output.truncate()
        self.assertEqual(self.post(headers={DCaddy.VISITOR_HEADER: '192.0.2.99',
                                           'X-Forwarded-For': '192.0.2.98'},
                                   json=self.payload).status_code, 204)
        self.assert_events(['collection_request'])

    def test_invalid_or_missing_attribution_publishes_neither_signal(self):
        for headers in ({}, {DCaddy.VISITOR_HEADER: 'bad'},
                        {DCaddy.VISITOR_HEADER: '192.0.2.1, 192.0.2.2'}):
            with self.subTest(headers=headers):
                self.assertEqual(self.post(peer='127.0.0.1', headers=headers,
                                           json=self.payload).status_code, 400)
        self.assertEqual(self.records(), [])
        self.collector.record.assert_not_called()

    def test_health_preflight_counter_reads_and_other_routes_emit_nothing(self):
        self.assertEqual(self.client.get('/health').status_code, 204)
        self.assertEqual(self.client.head('/health').status_code, 204)
        self.assertEqual(self.client.options('/count', headers={
            'Origin': DMyCount.ORIGINS[0], 'Access-Control-Request-Method': 'POST',
        }).status_code, 204)
        with patch('mycount.interface.CollectorHttp.CountVisits') as count:
            count.return_value.count.return_value = 1
            self.assertEqual(self.client.get('/get_count?site=mycount', headers={
                'Origin': DMyCount.ORIGINS[0]}).status_code, 200)
        self.assertEqual(self.client.post('/other').status_code, 404)
        self.assertEqual(self.client.get('/count', headers={
            'Origin': DMyCount.ORIGINS[0]}).status_code, 405)
        self.assertEqual(self.records(), [])

    def test_dependency_failures_are_not_malformed_payload_events(self):
        for error in (GeoIpUnavailable('offline'), pymysql.OperationalError(2003, 'offline')):
            with self.subTest(error=type(error)), self.assertLogs(level='ERROR'):
                self.output.seek(0)
                self.output.truncate()
                self.collector.record.side_effect = error
                self.assertEqual(self.post(json=self.payload).status_code, 503)
                self.assert_events(['collection_request'])

    def test_unexpected_handler_error_restores_request_context(self):
        self.collector.record.side_effect = RuntimeError('bug')
        with self.assertRaises(RuntimeError):
            self.post(json=self.payload)
        self.assert_events(['collection_request'])
        with self.assertRaises(RuntimeError):
            self.events.emit(DSecurityEvents.COLLECTION_REQUEST)

    def test_separate_app_instances_publish_all_requests_without_enforcing_a_threshold(self):
        other = Client(CollectorHttp(self.collector, DMyCount.ORIGINS, self.events))
        for index in range(60):
            client = self.client if index % 2 else other
            payload = dict(self.payload, url=DMyCount.ORIGINS[0] + f'/page-{index}')
            response = client.post('/count', json=payload, headers={
                'Origin': DMyCount.ORIGINS[0]}, environ_overrides={'REMOTE_ADDR': '192.0.2.1'})
            self.assertEqual(response.status_code, 204)
        self.assert_events(['collection_request'] * 60)


class SecurityLoggerCompositionTests(unittest.TestCase):
    def test_gunicorn_application_writes_exactly_one_unprefixed_record_per_event(self):
        logger = logging.getLogger(DSecurityEvents.LOGGER)
        old = (logger.handlers, logger.level, logger.propagate)
        self.addCleanup(self.restore_logger, logger, old)
        output = io.StringIO()
        with redirect_stderr(output):
            # load() creates the real application without starting Gunicorn or a database.
            application = MyCountServer.load(object.__new__(MyCountServer))
            application = MyCountServer.load(object.__new__(MyCountServer))
            response = Client(application).post('/count', data='{', content_type='application/json',
                headers={'Origin': DMyCount.ORIGINS[0], DCaddy.VISITOR_HEADER: '192.0.2.1'},
                environ_overrides={'REMOTE_ADDR': '127.0.0.1'})
        self.assertEqual(response.status_code, 400)
        records = output.getvalue().splitlines()
        self.assertEqual(len(records), 2)
        self.assertRegex(records[0], r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} '
                         r'SECURITY event=collection_request ip=192\.0\.2\.1$')
        self.assertTrue(records[1].endswith('SECURITY event=malformed_payload ip=192.0.2.1'))
        self.assertFalse(logger.propagate)

    @staticmethod
    def restore_logger(logger, old):
        logger.handlers, level, logger.propagate = old
        logger.setLevel(level)
