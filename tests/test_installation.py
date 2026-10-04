"""Exercise deployment scripts without touching host services or data."""

from contextlib import ExitStack, redirect_stdout
import io
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from mycount.constants.DCaddy import DCaddy
from mycount.constants.DGeoIp import DGeoIp
from mycount.constants.DMyCount import DMyCount
from mycount.constants.DRouterMappings import DRouterMappings


ROOT = Path(__file__).resolve().parents[1]


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(TemporaryDirectory()))
        self.config = self.root / 'Caddyfile'
        self.site = self.root / 'mycount.caddy'
        self.app = self.root / 'prod' / 'mycount'
        self.app.mkdir(parents=True)
        (self.app / 'application.py').write_text('installed')
        self.cron = self.root / 'cron'
        self.cron.write_text('schedule')
        self.unit_dir = self.root / 'systemd'
        self.unit_dir.mkdir()
        self.unit = self.unit_dir / DMyCount.SERVICE_UNIT
        self.unit.write_text('unit')
        self.control_unit = self.unit_dir / 'mycount-control.service'
        self.control_unit.write_text('unit')
        self.router_unit = self.unit_dir / DRouterMappings.SERVICE_UNIT
        self.router_unit.write_text('unit')
        self.credentials = self.root / 'database.env'
        self.credentials.write_text('preserve credentials')
        self.site.write_text('previous site')
        self.other_sites = ':80 {\n    respond "other site"\n}\n'
        self.config.write_text(self.other_sites + f'import {self.site}\n')
        for cls, key, value in (
            (DCaddy, 'CONFIG', str(self.config)),
            (DCaddy, 'SITE_CONFIG', str(self.site)),
            (DMyCount, 'BASE_DIR', str(self.app)),
            (DMyCount, 'DATABASE_ENV', str(self.credentials)),
            (DGeoIp, 'CRON_FILE', str(self.cron)),
        ):
            self.stack.enter_context(patch.object(cls, key, value))
        self.run = self.stack.enter_context(patch('subprocess.run'))
        self.run.return_value = subprocess.CompletedProcess([], 0)
        self.router = self.stack.enter_context(patch('mycount.interface.RouterMappings.RouterMappings.forward'))
        self.stack.enter_context(redirect_stdout(io.StringIO()))

    def execute(self, script):
        source = (ROOT / 'scripts' / script).read_text().split("<<'PY'\n", 1)[1].split('\nPY', 1)[0]
        source = source.replace("'/opt/prod'", repr(str(self.app.parent)))
        source = source.replace("'/etc/systemd/system'", repr(str(self.unit_dir)))
        exec(compile(source, script, 'exec'), {'__name__': '__main__'})

    def test_uninstall_is_repeatable_and_preserves_data_and_shared_sites(self):
        self.execute('uninstall.sh')
        self.execute('uninstall.sh')
        self.assertEqual(self.config.read_text(), self.other_sites)
        self.assertEqual(self.credentials.read_text(), 'preserve credentials')
        for path in (self.app, self.cron, self.unit, self.control_unit, self.router_unit, self.site):
            self.assertFalse(path.exists())
        commands = [call.args[0] for call in self.run.call_args_list]
        self.assertIn(['systemctl', 'disable', '--now', DMyCount.SERVICE_UNIT], commands)
        self.assertIn(['systemctl', 'disable', '--now', 'mycount-control.service'], commands)
        self.assertEqual(commands.count(['bash', 'scripts/clear-upnpc-routes.sh']), 2)
        self.assertLess(commands.index(['systemctl', 'disable', '--now', DRouterMappings.SERVICE_UNIT]),
                        commands.index(['bash', 'scripts/clear-upnpc-routes.sh']))
        self.assertFalse(any(command[0] in ('mariadb', 'userdel', 'groupdel', 'upnpc') for command in commands))

    def test_uninstall_clears_routes_before_removing_application(self):
        def run(command, **kwargs):
            if command == ['bash', 'scripts/clear-upnpc-routes.sh']:
                self.assertTrue((self.app / 'application.py').exists())
                self.assertFalse(self.unit.exists())
                self.assertFalse(self.control_unit.exists())
                self.assertFalse(self.router_unit.exists())
            return subprocess.CompletedProcess(command, 0)

        self.run.side_effect = run
        self.execute('uninstall.sh')
        self.assertFalse(self.app.exists())
        self.assertIn(['bash', 'scripts/clear-upnpc-routes.sh'],
                      [call.args[0] for call in self.run.call_args_list])

    def test_uninstall_router_cleanup_failure_preserves_application_for_retry(self):
        def run(command, **kwargs):
            if command == ['bash', 'scripts/clear-upnpc-routes.sh']:
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0)

        self.run.side_effect = run
        with self.assertRaises(subprocess.CalledProcessError):
            self.execute('uninstall.sh')
        self.assertTrue((self.app / 'application.py').exists())
        self.assertEqual(self.credentials.read_text(), 'preserve credentials')

    def test_uninstall_validation_failure_leaves_installation_intact(self):
        original = self.config.read_text()
        self.run.side_effect = subprocess.CalledProcessError(1, 'caddy')
        with self.assertRaises(subprocess.CalledProcessError):
            self.execute('uninstall.sh')
        self.assertEqual(self.config.read_text(), original)
        for path in (self.app, self.cron, self.unit, self.control_unit, self.router_unit, self.site):
            self.assertTrue(path.exists())

    def test_uninstall_preserves_marketing_screenshots(self):
        screenshots = self.app / 'pages' / 'marketing'
        screenshots.mkdir(parents=True)
        (screenshots / 'saved.png').write_bytes(b'screenshot')
        (self.app / 'pages' / 'other.md').write_text('remove')
        self.execute('uninstall.sh')
        self.execute('uninstall.sh')
        self.assertEqual((screenshots / 'saved.png').read_bytes(), b'screenshot')
        self.assertFalse((self.app / 'application.py').exists())
        self.assertFalse((self.app / 'pages' / 'other.md').exists())

    def test_uninstall_reload_failure_restores_config(self):
        original = self.config.read_text()
        self.run.side_effect = [subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0),
                                subprocess.CalledProcessError(1, 'systemctl')]
        with self.assertRaises(subprocess.CalledProcessError):
            self.execute('uninstall.sh')
        self.assertEqual(self.config.read_text(), original)
        self.assertTrue(self.site.exists())
        self.assertTrue(self.app.exists())

    def test_uninstall_rejects_symlink_application(self):
        elsewhere = self.root / 'elsewhere'
        self.app.rename(elsewhere)
        self.app.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaises(SystemExit):
            self.execute('uninstall.sh')
        self.assertTrue((elsewhere / 'application.py').exists())
        self.run.assert_not_called()

    def test_caddy_install_is_repeatable_and_validates_beside_config(self):
        def run(command, **kwargs):
            if command[0] == 'caddy':
                candidate = Path(command[command.index('--config') + 1])
                self.assertEqual(candidate.parent, self.config.parent)
                self.assertIn(self.other_sites.strip(), candidate.read_text())
            return subprocess.CompletedProcess(command, 0)
        self.run.side_effect = run
        original = self.config.read_text()
        self.execute('install-caddy.sh')
        self.execute('install-caddy.sh')
        self.assertEqual(self.config.read_text().count(f'import {self.site}'), 1)
        self.assertIn(self.other_sites.strip(), self.config.read_text())
        self.assertEqual(self.config.with_name('Caddyfile.before-mycount').read_text(), original)
        self.assertIn('reverse_proxy', self.site.read_text())
        self.assertEqual(self.router.call_count, 2)
        self.router.assert_called_with((80, 443))

    def test_caddy_reload_failure_restores_previous_files(self):
        original = self.config.read_text()
        self.run.side_effect = [subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0),
                                subprocess.CalledProcessError(1, 'systemctl')]
        with self.assertRaises(subprocess.CalledProcessError):
            self.execute('install-caddy.sh')
        self.assertEqual(self.config.read_text(), original)
        self.assertEqual(self.site.read_text(), 'previous site')

    def test_full_setup_removes_legacy_geoip_schedule_and_runner(self):
        legacy = self.app / 'scripts/update-geoip.sh'
        legacy.parent.mkdir()
        legacy.write_text('old importer')
        source = (ROOT / 'scripts/install-services.sh').read_text().split('render_definitions() {', 1)[1]
        source = source.split("<<'PY'\n", 1)[1].split('\nPY', 1)[0]
        with patch('sys.argv', ['installer', str(ROOT), 'true']):
            exec(compile(source, 'install-services.sh', 'exec'), {'__name__': '__main__'})
        self.assertFalse(self.cron.exists())
        self.assertFalse(legacy.exists())
        self.assertEqual(self.credentials.read_text(), 'preserve credentials')


if __name__ == '__main__':
    unittest.main()
