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
    def test_clear_deletes_only_requested_tcp_ports(self, run):
        remaining = LAN + " 0 UDP 80->192.168.0.99:80 'other' '' 0\n 1 TCP 22->192.168.0.99:22 'ssh' '' 0\n"
        listings = iter((BEFORE, remaining))
        run.side_effect = lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, next(listings) if command == ['upnpc', '-l'] else '')
        RouterMappings().clear((80, 443))
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            ['upnpc', '-l'], ['upnpc', '-d', '80', 'TCP'],
            ['upnpc', '-d', '443', 'TCP'], ['upnpc', '-l']])

    @patch('mycount.interface.RouterMappings.subprocess.run')
    def test_clear_deletes_udp_only_when_tcp_destination_matches(self, run):
        before = BEFORE + " 4 UDP 443->192.168.0.86:443 'matching' '' 0\n"
        remaining = LAN + " 0 UDP 80->192.168.0.99:80 'other' '' 0\n 1 TCP 22->192.168.0.99:22 'ssh' '' 0\n"
        listings = iter((before, remaining))
        run.side_effect = lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, next(listings) if command == ['upnpc', '-l'] else '')
        RouterMappings().clear((80, 443))
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            ['upnpc', '-l'], ['upnpc', '-d', '80', 'TCP'],
            ['upnpc', '-d', '443', 'TCP'], ['upnpc', '-d', '443', 'UDP'], ['upnpc', '-l']])

    @patch('mycount.interface.RouterMappings.subprocess.run')
    def test_clear_preserves_udp_with_different_internal_port_or_no_tcp(self, run):
        before = LAN + " 0 TCP 80->192.168.0.86:80 'tcp' '' 0\n 1 UDP 80->192.168.0.86:8080 'other port' '' 0\n 2 UDP 443->192.168.0.86:443 'udp only' '' 0\n"
        after = '\n'.join(line for line in before.splitlines() if ' TCP ' not in line) + '\n'
        listings = iter((before, after))
        run.side_effect = lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, next(listings) if command == ['upnpc', '-l'] else '')
        RouterMappings().clear((80, 443))
        self.assertEqual([call.args[0] for call in run.call_args_list], [
            ['upnpc', '-l'], ['upnpc', '-d', '80', 'TCP'], ['upnpc', '-l']])

    @patch('mycount.interface.RouterMappings.subprocess.run')
    def test_clear_detects_matching_udp_remaining(self, run):
        before = BEFORE + " 4 UDP 443->192.168.0.86:443 'matching' '' 0\n"
        after = LAN + " 0 UDP 443->192.168.0.86:443 'matching' '' 0\n"
        listings = iter((before, after))
        run.side_effect = lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, next(listings) if command == ['upnpc', '-l'] else '')
        with self.assertRaisesRegex(RuntimeError, 'UDP port 443 mapping remains'):
            RouterMappings().clear((80, 443))

    @patch('mycount.interface.RouterMappings.subprocess.run')
    def test_clear_absent_ports_is_repeatable(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, LAN)
        RouterMappings().clear((80, 443))
        RouterMappings().clear((80, 443))
        self.assertEqual([call.args[0] for call in run.call_args_list], [['upnpc', '-l']] * 4)

    @patch('mycount.interface.RouterMappings.subprocess.run')
    def test_clear_detects_router_refusing_deletion(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, BEFORE)
        with self.assertRaisesRegex(RuntimeError, 'mapping remains'):
            RouterMappings().clear((80, 443))

    @patch('mycount.interface.RouterMappings.subprocess.run')
    def test_clear_discovery_failure_prevents_deletion(self, run):
        run.side_effect = subprocess.CalledProcessError(1, 'upnpc')
        with self.assertRaises(subprocess.CalledProcessError):
            RouterMappings().clear((80, 443))
        run.assert_called_once_with(['upnpc', '-l'], check=True, capture_output=True, text=True)

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
