"""Verify UPnP replacement against captured router listings without changing a router."""

import subprocess
import unittest
from unittest.mock import patch

from mycount.interface.RouterMappings import RouterMappings


LAN = 'Local LAN ip address : 192.168.0.42\n'
BEFORE = LAN + " 0 TCP 80->192.168.0.86:80 'old' '' 0\n 1 TCP 443->192.168.0.86:443 'old' '' 0\n 2 UDP 80->192.168.0.99:80 'other' '' 0\n 3 TCP 22->192.168.0.99:22 'ssh' '' 0\n"
AFTER = LAN + " 0 TCP 80->192.168.0.42:80 'mycount' '' 0\n 1 TCP 443->192.168.0.42:443 'mycount' '' 0\n"


class RouterMappingsTests(unittest.TestCase):
    @patch('mycount.interface.RouterMappings.subprocess.run')
    def test_detects_host_and_replaces_only_requested_tcp_ports(self, run):
        listings = iter((BEFORE, AFTER))
        run.side_effect = lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, next(listings) if command == ['upnpc', '-l'] else '')
        RouterMappings().forward((80, 443))
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            ['upnpc', '-l'], ['upnpc', '-d', '80', 'TCP'],
            ['upnpc', '-a', '192.168.0.42', '80', '80', 'TCP'],
            ['upnpc', '-d', '443', 'TCP'],
            ['upnpc', '-a', '192.168.0.42', '443', '443', 'TCP'], ['upnpc', '-l']])

    @patch('mycount.interface.RouterMappings.subprocess.run')
    def test_absent_rules_are_added_without_deletion(self, run):
        listings = iter((LAN, AFTER))
        run.side_effect = lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, next(listings) if command == ['upnpc', '-l'] else '')
        RouterMappings().forward((80, 443))
        self.assertFalse(any('-d' in call.args[0] for call in run.call_args_list))

    @patch('mycount.interface.RouterMappings.subprocess.run')
    def test_router_silently_refusing_changes_is_reported(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, BEFORE)
        with self.assertRaisesRegex(RuntimeError, 'did not forward'):
            RouterMappings().forward((80, 443))

    @patch('mycount.interface.RouterMappings.subprocess.run')
    def test_missing_or_invalid_discovery_prevents_mutation(self, run):
        for listing in ('No IGD found', 'Local LAN ip address : 127.0.0.1\n'):
            run.reset_mock()
            run.return_value = subprocess.CompletedProcess([], 0, listing)
            with self.assertRaises((RuntimeError, ValueError)):
                RouterMappings().forward((80, 443))
            run.assert_called_once_with(['upnpc', '-l'], check=True, capture_output=True, text=True)

    @patch('mycount.interface.RouterMappings.subprocess.run')
    def test_failed_deletion_stops_before_adding(self, run):
        run.side_effect = [subprocess.CompletedProcess([], 0, BEFORE), subprocess.CalledProcessError(1, 'upnpc')]
        with self.assertRaises(subprocess.CalledProcessError):
            RouterMappings().forward((80, 443))
        self.assertEqual(run.call_count, 2)
