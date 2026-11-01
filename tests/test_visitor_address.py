import unittest
from unittest.mock import patch

from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from mycount.constants.DCaddy import DCaddy
from mycount.constants.DMyCount import DMyCount
from mycount.interface.VisitPayload import InvalidVisit
from mycount.interface.VisitorAddress import VisitorAddress


class VisitorAddressTests(unittest.TestCase):
    def request(self, peer, address):
        return Request(EnvironBuilder(headers={DCaddy.VISITOR_HEADER: address},
                                     environ_base={'REMOTE_ADDR': peer}).get_environ())

    def test_local_proxy(self):
        request = self.request('127.0.0.1', '2001:4860:4860::8888')
        self.assertEqual(VisitorAddress.resolve(request), '2001:4860:4860::8888')

    def test_proxy_address_uses_backend_interface(self):
        with patch.object(DMyCount, 'CMDB_NETWORK', (('backend', '127.0.0.2', 37000),)):
            self.assertEqual(VisitorAddress.resolve(self.request('127.0.0.2', '8.8.8.8')), '8.8.8.8')
            self.assertEqual(VisitorAddress.resolve(self.request('192.0.2.1', '8.8.8.8')), '192.0.2.1')

    def test_untrusted_peer_cannot_override_address(self):
        self.assertEqual(VisitorAddress.resolve(self.request('192.0.2.1', '8.8.8.8')), '192.0.2.1')

    def test_proxy_must_supply_one_address(self):
        with self.assertRaises(InvalidVisit):
            VisitorAddress.resolve(self.request('127.0.0.1', '8.8.8.8, 1.1.1.1'))

    def test_proxy_without_client_address_is_rejected(self):
        request = Request(EnvironBuilder(environ_base={'REMOTE_ADDR': '127.0.0.1'}).get_environ())
        with self.assertRaises(InvalidVisit):
            VisitorAddress.resolve(request)

    def test_numeric_sources_are_normalized(self):
        self.assertEqual(VisitorAddress.resolve(self.request('127.0.0.1', '2001:0DB8::0001')),
                         '2001:db8::1')
        self.assertEqual(VisitorAddress.resolve(self.request('2001:0DB8::0002', '192.0.2.1')),
                         '2001:db8::2')

    def test_missing_invalid_and_unusable_sources_are_rejected(self):
        for source in (None, '', 'not-an-address', '::1%lo', '0.0.0.0', '::', '224.0.0.1',
                       'ff02::1', '192.0.2.1:80', '192.0.2.1/24'):
            with self.subTest(source=source), self.assertRaises(InvalidVisit):
                VisitorAddress.resolve(self.request('127.0.0.1', source))

        for peer in (None, '', 'not-an-address', '::1%lo', '::'):
            with self.subTest(peer=peer), self.assertRaises(InvalidVisit):
                VisitorAddress.resolve(self.request(peer, '192.0.2.1'))
