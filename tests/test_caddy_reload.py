"""Reload an isolated Caddy instance across the pre-2.5 listener layout."""

from contextlib import ExitStack, redirect_stdout
import io
import os
from pathlib import Path
import shutil
import socket
import subprocess
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from mycount.constants.DCaddy import DCaddy
from mycount.interface.Network import Network


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('caddy'), 'Caddy is required for the live reload regression test.')
class CaddyReloadTests(unittest.TestCase):
    def test_upgrade_reuses_existing_wildcard_listeners(self):
        self.exercise_reload()

    def test_explicit_ipv4_wildcard_reproduces_reload_failure(self):
        self.exercise_reload(explicit_wildcard=True)

    def exercise_reload(self, explicit_wildcard=False):
        with ExitStack() as stack:
            root = Path(stack.enter_context(TemporaryDirectory()))
            # Reserve distinct ephemeral ports, then release them for this Caddy instance.
            reservations = [socket.socket() for _ in range(3)]
            try:
                for listener in reservations:
                    listener.bind(('127.0.0.1', 0))
                admin_port, http_port, https_port = [listener.getsockname()[1] for listener in reservations]
            finally:
                for listener in reservations:
                    listener.close()
            config = root / 'Caddyfile'
            site = root / 'mycount.caddy'
            config.write_text('{' + f'\n    admin 127.0.0.1:{admin_port}\n'
                              '    local_certs\n    skip_install_trust\n'
                              '    auto_https disable_redirects\n}\n'
                              f':{http_port} {{\n    respond "shared site"\n}}\nimport {site}\n')
            site.write_text(f'https://localhost:{https_port} {{\n    respond "old collector"\n}}\n')
            environment = {**os.environ, 'XDG_DATA_HOME': str(root / 'data'),
                           'XDG_CONFIG_HOME': str(root / 'config')}
            log = stack.enter_context((root / 'caddy.log').open('w+'))
            process = subprocess.Popen(['caddy', 'run', '--config', str(config), '--adapter', 'caddyfile'],
                                       env=environment, stdout=log, stderr=subprocess.STDOUT)

            def stop():
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            stack.callback(stop)
            opener = build_opener(ProxyHandler({}))
            deadline = time.monotonic() + 10
            while True:
                try:
                    with opener.open(f'http://127.0.0.1:{admin_port}/config/', timeout=0.2):
                        break
                except (URLError, TimeoutError):
                    if process.poll() is not None or time.monotonic() >= deadline:
                        log.seek(0)
                        self.fail('Test Caddy failed to start: ' + log.read())
                    time.sleep(0.05)
            bindings = {'http': ('0.0.0.0', http_port), 'https': ('0.0.0.0', https_port),
                        'backend': ('127.0.0.1', 36666)}
            for key, value in (('CONFIG', str(config)), ('SITE_CONFIG', str(site)), ('HOSTNAME', 'localhost')):
                stack.enter_context(patch.object(DCaddy, key, value))
            stack.enter_context(patch.object(Network, 'binding', side_effect=bindings.__getitem__))
            stack.enter_context(patch('mycount.interface.RouterMappings.RouterMappings.forward'))
            run = subprocess.run

            def command(arguments, **kwargs):
                if arguments[0] == 'systemctl':
                    return subprocess.CompletedProcess(arguments, 0)
                return run(arguments, env=environment, **kwargs)

            stack.enter_context(patch('subprocess.run', side_effect=command))
            source = (ROOT / 'scripts/install-caddy.sh').read_text().split("<<'PY'\n", 1)[1].split('\nPY', 1)[0]
            if explicit_wildcard:
                read_text = Path.read_text

                def old_template(path, *args, **kwargs):
                    text = read_text(path, *args, **kwargs)
                    if path == Path('caddy/mycount.caddy'):
                        text = text.replace('@HTTP_BIND@', 'bind 0.0.0.0')
                        text = text.replace('@HTTPS_BIND@', 'bind 0.0.0.0')
                    return text

                stack.enter_context(patch.object(Path, 'read_text', old_template))
            with redirect_stdout(io.StringIO()):
                if explicit_wildcard:
                    with self.assertRaises(subprocess.CalledProcessError):
                        exec(compile(source, 'install-caddy.sh', 'exec'), {})
                else:
                    exec(compile(source, 'install-caddy.sh', 'exec'), {})
            self.assertIsNone(process.poll())
            if explicit_wildcard:
                self.assertIn('respond "old collector"', site.read_text())
                return
            with opener.open(f'http://127.0.0.1:{http_port}/', timeout=1) as response:
                self.assertEqual(response.read(), b'shared site')
            self.assertNotIn('bind 0.0.0.0', site.read_text())
