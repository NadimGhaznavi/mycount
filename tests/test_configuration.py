"""Verify production configuration creation, validation, and restart semantics."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from mycount.constants.DMyCount import DMyCount
from mycount.interface.Configuration import Configuration
from mycount.interface.Network import Network


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        base = patch.object(DMyCount, 'BASE_DIR', str(self.root))
        base.start()
        self.addCleanup(base.stop)
        self.addCleanup(Network._bindings.cache_clear)
        self.path = self.root / DMyCount.CONFIG_FILE
        self.path.parent.mkdir()

    def write(self, values):
        self.path.write_text(json.dumps(values))

    def read(self):
        return Configuration.read(self.path, DMyCount.CMDB_NETWORK)

    def test_install_creates_defaults_and_readable_permissions(self):
        self.path.parent.rmdir()
        Configuration.install()
        self.assertEqual(self.read(), {use: (interface, port) for use, interface, port in DMyCount.CMDB_NETWORK})
        self.assertEqual(set(json.loads(self.path.read_text())['network']), {'http', 'https', 'report', 'backend'})
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o755)

    def test_reinstall_preserves_custom_file_bytes(self):
        self.write({'network': {'report': {'interface': '127.0.0.2', 'port': 62000}}})
        original = self.path.read_bytes()
        Configuration.install()
        Configuration.install()
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.read()['report'], ('127.0.0.2', 62000))

    def test_partial_overrides_and_missing_file_use_independent_defaults(self):
        defaults = self.read()
        self.write({'network': {'report': {'port': 62000}}})
        configured = self.read()
        self.assertEqual(configured['report'], ('0.0.0.0', 62000))
        self.assertEqual(defaults['report'], ('0.0.0.0', 61777))
        self.assertEqual(configured['backend'], defaults['backend'])
        configured['backend'] = ('127.0.0.2', 12345)
        self.assertEqual(self.read()['backend'], defaults['backend'])

    def test_wildcard_binding_keeps_local_proxy_destination(self):
        from mycount.interface.VisitorAddress import VisitorAddress
        from mycount.constants.DCaddy import DCaddy
        from werkzeug.test import EnvironBuilder
        from werkzeug.wrappers import Request
        self.write({'network': {'backend': {'interface': '0.0.0.0'}}})
        self.assertEqual(Network.binding('backend'), ('0.0.0.0', 36666))
        self.assertEqual(Network.destination('backend'), ('127.0.0.1', 36666))
        request = Request(EnvironBuilder(headers={DCaddy.VISITOR_HEADER: '8.8.8.8'},
                                        environ_base={'REMOTE_ADDR': '127.0.0.1'}).get_environ())
        self.assertEqual(VisitorAddress.resolve(request), '8.8.8.8')

    def test_changes_are_loaded_on_process_restart(self):
        self.write({'network': {'report': {'port': 62000}}})
        self.assertEqual(Network.binding('report')[1], 62000)
        self.write({'network': {'report': {'port': 62001}}})
        self.assertEqual(Network.binding('report')[1], 62000)
        Network._bindings.cache_clear()  # A new service process starts with an empty cache.
        self.assertEqual(Network.binding('report')[1], 62001)

    def test_invalid_configurations_identify_field(self):
        cases = [([], 'network settings'), ({'netwrok': {}}, 'network settings'),
                 ({'network': []}, 'network must be an object'),
                 ({'network': {'typo': {}}}, 'network.typo'),
                 ({'network': {'report': []}}, 'network.report'),
                 ({'network': {'report': {'host': '127.0.0.1'}}}, 'network.report')]
        for interface in (None, 123, '', 'localhost', '999.0.0.1', '::1'):
            cases.append(({'network': {'report': {'interface': interface}}}, 'network.report.interface'))
        for port in (None, True, '1234', 0, -1, 65536, 1.5):
            cases.append(({'network': {'report': {'port': port}}}, 'network.report.port'))
        for values, field in cases:
            with self.subTest(values=values):
                self.write(values)
                with self.assertRaisesRegex(ValueError, field):
                    self.read()

    def test_invalid_existing_file_is_preserved_and_rejected_by_install(self):
        self.path.write_text('{bad json')
        with self.assertRaisesRegex(ValueError, 'invalid JSON'):
            Configuration.install()
        self.assertEqual(self.path.read_text(), '{bad json')

    def test_restart_applies_config_to_caddy_and_services(self):
        import subprocess
        from mycount.constants.DControl import DControl
        from mycount.constants.DRouterMappings import DRouterMappings
        source = (Path(__file__).resolve().parents[1] / 'scripts/restart.sh').read_text()
        source = source.split(".venv/bin/python -B - <<'PY'\n", 1)[1].split('\nPY', 1)[0]
        with patch('subprocess.run') as run, patch('builtins.print'):
            self.write({'network': {'report': {'port': 62000}}})
            exec(compile(source, 'restart.sh', 'exec'), {})
            self.assertEqual([call.args[0] for call in run.call_args_list], [
                ['bash', 'scripts/install-caddy.sh'],
                ['systemctl', 'restart', DMyCount.SERVICE_UNIT, DControl.SERVICE_UNIT, DRouterMappings.SERVICE_UNIT],
            ])
            run.reset_mock()
            self.path.write_text('{invalid')
            with self.assertRaises(ValueError):
                exec(compile(source, 'restart.sh', 'exec'), {})
            run.assert_not_called()
            self.write({})
            run.side_effect = subprocess.CalledProcessError(1, 'caddy')
            with self.assertRaises(subprocess.CalledProcessError):
                exec(compile(source, 'restart.sh', 'exec'), {})
            self.assertEqual(run.call_count, 1)
