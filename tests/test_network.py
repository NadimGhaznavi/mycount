"""Verify listener consumers follow the CMDB inventory by use."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import runpy
import unittest
from unittest.mock import Mock, patch

from mycount.constants.DControl import DControl
from mycount.constants.DMyCount import DMyCount
from mycount.interface.Network import Network
from mycount.server.ControlServer import main
from mycount.server.MyCountServer import MyCountServer


ROOT = Path(__file__).resolve().parents[1]
NETWORK = (
    ('report', '192.0.2.10', 62000),
    ('backend', '127.0.0.2', 37000),
    ('https', '192.0.2.11', 8443),
    ('http', '192.0.2.12', 8080),
)


class NetworkTests(unittest.TestCase):
    def setUp(self):
        inventory = patch.object(DMyCount, 'CMDB_NETWORK', NETWORK)
        inventory.start()
        self.addCleanup(inventory.stop)

    def test_unknown_use_is_a_configuration_error(self):
        with self.assertRaises(KeyError):
            Network.binding('missing')

    def test_backend_binding(self):
        self.assertEqual(MyCountServer().cfg.bind, ['127.0.0.2:37000'])

    def test_report_binding_and_explicit_override(self):
        for arguments, expected in (
            ([], ('192.0.2.10', 62000)),
            (['--host', '127.0.0.3', '--port', '62001'], ('127.0.0.3', 62001)),
        ):
            with self.subTest(arguments=arguments), patch('sys.argv', ['control', *arguments]):
                with patch('mycount.server.ControlServer.ThreadingHTTPServer') as server:
                    server.return_value.__enter__.return_value.serve_forever.side_effect = KeyboardInterrupt
                    with patch('mycount.server.ControlServer.signal.signal'), redirect_stdout(io.StringIO()):
                        main()
                    self.assertEqual(server.call_args.args[0], expected)

    def test_health_checks_use_configured_addresses_and_ports(self):
        script = (ROOT / 'scripts/install-services.sh').read_text().split('check_health() {', 1)[1]
        source = script.split("<<'PY'\n", 1)[1].split('\nPY', 1)[0]
        for report_interface, report_host in (('192.0.2.10', '192.0.2.10'), ('0.0.0.0', '127.0.0.1')):
            inventory = (('report', report_interface, 62000), *NETWORK[1:])
            with self.subTest(interface=report_interface), patch.object(DMyCount, 'CMDB_NETWORK', inventory):
                with patch('urllib.request.build_opener') as build:
                    opener = build.return_value
                    opener.open.return_value.__enter__.side_effect = [Mock(status=204), Mock(status=200)]
                    with patch('sys.argv', ['installer', DMyCount.SERVICE_UNIT, DControl.SERVICE_UNIT]):
                        with redirect_stdout(io.StringIO()):
                            exec(compile(source, 'install-services.sh', 'exec'), {})
                    self.assertEqual([call.args[0] for call in opener.open.call_args_list],
                                     ['http://127.0.0.2:37000/health', f'http://{report_host}:62000/health'])

    def test_local_smoke_check_uses_https_binding(self):
        script = runpy.run_path(str(ROOT / 'scripts/test_ax3l.py'))
        with patch('subprocess.run') as run, redirect_stdout(io.StringIO()):
            run.return_value.stdout = 'HTTP/2 204\n\n'
            script['request']('GET', '/health', True)
        command = run.call_args.args[0]
        self.assertIn('count.osoyalce.com:8443:192.0.2.11', command)
        self.assertEqual(command[-1], 'https://count.osoyalce.com:8443/health')

    def test_router_cleanup_uses_inventory_ports(self):
        script = (ROOT / 'scripts/clear-upnpc-routes.sh').read_text()
        source = script.split("<<'PY'\n", 1)[1].split('\nPY', 1)[0]
        with patch('mycount.interface.RouterMappings.RouterMappings.clear') as clear:
            with redirect_stdout(io.StringIO()):
                exec(compile(source, 'clear-upnpc-routes.sh', 'exec'), {})
        clear.assert_called_once_with((8080, 8443))
