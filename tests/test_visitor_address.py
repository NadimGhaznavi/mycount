import unittest

from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from mycount.constants.DCaddy import DCaddy
from mycount.interface.VisitPayload import InvalidVisit
from mycount.interface.VisitorAddress import VisitorAddress


class VisitorAddressTests(unittest.TestCase):
    def request(self, peer, address):
        return Request(EnvironBuilder(headers={DCaddy.VISITOR_HEADER: address},
                                     environ_base={'REMOTE_ADDR': peer}).get_environ())

    def test_local_proxy(self):
        request = self.request('127.0.0.1', '2001:4860:4860::8888')
        self.assertEqual(VisitorAddress.resolve(request), '2001:4860:4860::8888')

    def test_untrusted_peer_cannot_override_address(self):
        self.assertEqual(VisitorAddress.resolve(self.request('192.0.2.1', '8.8.8.8')), '192.0.2.1')

    def test_proxy_must_supply_one_address(self):
        with self.assertRaises(InvalidVisit):
            VisitorAddress.resolve(self.request('127.0.0.1', '8.8.8.8, 1.1.1.1'))

    def test_direct_local_request(self):
        request = Request(EnvironBuilder(environ_base={'REMOTE_ADDR': '127.0.0.1'}).get_environ())
        self.assertEqual(VisitorAddress.resolve(request), '127.0.0.1')
