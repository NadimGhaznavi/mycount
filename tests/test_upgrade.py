"""Run upgrade shell orchestration with isolated, inert command substitutes."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.checkout = self.root / 'checkout'
        scripts = self.checkout / 'scripts'
        scripts.mkdir(parents=True)
        # Exercise orchestration as an ordinary user; all privileged commands
        # and embedded Python deployment steps are replaced below.
        for name in ('upgrade.sh', 'install-services.sh'):
            source = (ROOT / 'scripts' / name).read_text().replace('$EUID', '0')
            self.executable(scripts / name, source)
        self.app = self.root / 'installed'
        (self.app / '.venv/bin').mkdir(parents=True)
        (self.app / 'scripts').mkdir()
        self.credentials = self.root / 'database.env'
        self.credentials.write_text('retained credentials')
        self.log = self.root / 'commands'
        binaries = self.root / 'bin'
        binaries.mkdir()
        python = binaries / 'python3'
        self.executable(python, '''#!/bin/bash
input=$(cat)
if [[ $input == *'print(DMyCount.BASE_DIR)'* ]]; then
    printf '%s\\n' "$TEST_APP" "$TEST_CREDENTIALS" mycount mycount-server.service mycount-control.service mycount-router.service
elif [[ $input == *'upgrade_targets(previous'* ]]; then
    echo flags >> "$TEST_LOG"
    if [[ ${TEST_FLAGS_FAILURE:-0} != 0 ]]; then exit 1; fi
    printf '%s\\n' "${TEST_FLAGS-filesystem
listener
report-server}"
elif [[ $input == *'Credentials do not belong'* ]]; then
    echo credentials >> "$TEST_LOG"
    exit "${TEST_CREDENTIAL_FAILURE:-0}"
else
    if [[ $input == *'Applying database schemas'* || $input == *'VisitorSchema(db).apply()'* ]]; then
        echo schema >> "$TEST_LOG"
    elif [[ $input == *'.complete(DMyCount.VERSION)'* ]]; then
        echo version-committed >> "$TEST_LOG"
    elif [[ $input == *'files.copy_application(targets)'* ]]; then
        echo "copy $*" >> "$TEST_LOG"
    elif [[ $input == *'opener = build_opener'* ]]; then
        echo "health $*" >> "$TEST_LOG"
        exit "${TEST_HEALTH_FAILURE:-0}"
    elif [[ $input == *"target = Path('/etc/systemd/system', name)"* ]]; then
        echo "definitions $*" >> "$TEST_LOG"
    else
        echo python-step >> "$TEST_LOG"
    fi
fi
''')
        shutil.copy2(python, self.app / '.venv/bin/python')
        for name in ('getent', 'systemctl', 'systemd-analyze', 'install'):
            self.executable(binaries / name, '#!/bin/bash\necho "' + name + ' $*" >> "$TEST_LOG"\n')
        self.executable(self.app / 'scripts/update-geoip.sh', '#!/bin/bash\necho geoip >> "$TEST_LOG"\n')
        self.executable(scripts / 'install-caddy.sh', '#!/bin/bash\necho caddy >> "$TEST_LOG"\nexit "${TEST_CADDY_FAILURE:-0}"\n')
        self.env = {**os.environ, 'PATH': str(binaries) + os.pathsep + os.environ['PATH'],
                    'TEST_APP': str(self.app), 'TEST_CREDENTIALS': str(self.credentials),
                    'TEST_LOG': str(self.log)}

    def executable(self, path, source):
        path.write_text(source)
        path.chmod(0o755)

    def run_script(self, script='upgrade.sh', *args):
        return subprocess.run([str(self.checkout / 'scripts' / script), *args],
                              cwd=self.root, env=self.env, capture_output=True, text=True, timeout=10)

    def test_upgrade_skips_geoip_and_restarts_service(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.log.read_text().splitlines()
        self.assertNotIn('geoip', commands)
        self.assertIn('systemctl enable --now mycount-server.service', commands)
        self.assertIn('systemctl enable --now mycount-router.service', commands)
        self.assertIn('systemctl enable --now mycount-control.service', commands)
        self.assertIn('caddy', commands)
        self.assertIn('Upgraded MyCount', result.stdout)
        self.assertIn(f'install -d -m 755 -o mycount -g mycount -- {self.app}/pages/marketing', commands)
        self.assertEqual(self.credentials.read_text(), 'retained credentials')

    def test_display_only_skips_listener_and_shared_setup(self):
        self.env['TEST_FLAGS'] = 'report-server'
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.log.read_text().splitlines()
        self.assertIn('systemctl enable --now mycount-control.service', commands)
        self.assertNotIn('systemctl enable --now mycount-server.service', commands)
        self.assertNotIn('systemctl stop mycount-server.service', commands)
        self.assertNotIn('schema', commands)
        self.assertNotIn('caddy', commands)
        self.assertNotIn('systemctl enable --now cron.service', commands)
        self.assertIn('version-committed', commands)
        self.assertTrue(any(line.startswith('copy ') and line.endswith('report-server') for line in commands))
        self.assertTrue(any(line.startswith('health ') and line.endswith('mycount-control.service') for line in commands))

    def test_no_impact_does_not_restart_services(self):
        self.env['TEST_FLAGS'] = ''
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.log.read_text().splitlines()
        self.assertFalse(any(line.startswith(('systemctl', 'copy ', 'health ', 'definitions ')) for line in commands))
        self.assertNotIn('schema', commands)
        self.assertIn('version-committed', commands)

    def test_listener_only_skips_report_and_setup(self):
        self.env['TEST_FLAGS'] = 'listener'
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.log.read_text().splitlines()
        self.assertIn('systemctl enable --now mycount-server.service', commands)
        self.assertIn('systemctl enable --now mycount-router.service', commands)
        self.assertNotIn('systemctl enable --now mycount-control.service', commands)
        self.assertNotIn('schema', commands)
        self.assertNotIn('caddy', commands)
        self.assertTrue(any(line.startswith('health ') and line.endswith('mycount-server.service mycount-router.service') for line in commands))

    def test_health_failure_does_not_publish_release_metadata(self):
        self.env['TEST_FLAGS'] = 'report-server'
        self.env['TEST_HEALTH_FAILURE'] = '1'
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('version-committed', self.log.read_text())
        self.assertNotIn('Upgraded MyCount', result.stdout)

    def test_invalid_release_stops_before_deployment(self):
        self.env['TEST_FLAGS_FAILURE'] = '1'
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('systemctl', self.log.read_text())
        self.assertNotIn('version-committed', self.log.read_text())

    def test_install_uses_external_geoip_without_refresh_or_cron(self):
        result = self.run_script('install-services.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.log.read_text().splitlines()
        self.assertNotIn('geoip', commands)
        self.assertNotIn('systemctl enable --now cron.service', commands)

    def test_missing_installation_fails_before_deployment(self):
        self.credentials.unlink()
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Run install.sh first', result.stderr)
        self.assertFalse(self.log.exists())

    def test_invalid_credentials_fail_before_service_stop(self):
        self.env['TEST_CREDENTIAL_FAILURE'] = '1'
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('systemctl', self.log.read_text())
        self.assertNotIn('Upgraded MyCount', result.stdout)

    def test_deployment_failure_does_not_report_success(self):
        self.env['TEST_CADDY_FAILURE'] = '1'
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('Upgraded MyCount', result.stdout)
        self.assertNotIn('version-committed', self.log.read_text())

    def test_help_and_invalid_arguments_do_not_deploy(self):
        self.assertEqual(self.run_script('upgrade.sh', '--help').returncode, 0)
        self.assertEqual(self.run_script('upgrade.sh', '--unknown').returncode, 2)
        self.assertFalse(self.log.exists())
