#!/usr/bin/env bash
# Remove the deployment while preserving data and shared infrastructure.
set -euo pipefail
umask 022
if [[ ${1:-} == --help && $# == 1 ]]; then
    printf 'Usage: sudo scripts/uninstall.sh\nRemove MyCount services and application; preserve databases, credentials, accounts, and router mappings.\n'
    exit 0
fi
[[ $# == 0 && $EUID == 0 ]] || { printf 'Run scripts/uninstall.sh as root, without arguments.\n' >&2; exit 1; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python3 -B - <<'PY'
from pathlib import Path
import shutil
import subprocess
from tempfile import NamedTemporaryFile

from mycount.constants.DCaddy import DCaddy
from mycount.constants.DGeoIp import DGeoIp
from mycount.constants.DMyCount import DMyCount

application = Path(DMyCount.BASE_DIR)
if application.is_symlink() or application.parent != Path('/opt/prod') or application.name != 'mycount':
    raise SystemExit('Refusing to remove an unexpected application directory.')

config = Path(DCaddy.CONFIG)
site = Path(DCaddy.SITE_CONFIG)
if config.exists():
    original = config.read_text()
    directive = f'import {site}'
    updated = ''.join(line for line in original.splitlines(keepends=True) if line.strip() != directive)
    if updated != original:
        with NamedTemporaryFile(mode='w', prefix='.mycount-', suffix='.Caddyfile', dir=config.parent) as candidate:
            candidate.write(updated)
            candidate.flush()
            subprocess.run(['caddy', 'validate', '--config', candidate.name, '--adapter', 'caddyfile'], check=True)
        config.write_text(updated)
        try:
            if subprocess.run(['systemctl', 'is-active', '--quiet', DCaddy.SERVICE]).returncode == 0:
                subprocess.run(['systemctl', 'reload', DCaddy.SERVICE], check=True)
        except subprocess.CalledProcessError:
            config.write_text(original)
            raise
site.unlink(missing_ok=True)

# Remove the schedule first so no new refresh is launched during removal.
Path(DGeoIp.CRON_FILE).unlink(missing_ok=True)
unit = Path('/etc/systemd/system') / DMyCount.SERVICE_UNIT
if unit.exists():
    subprocess.run(['systemctl', 'disable', '--now', DMyCount.SERVICE_UNIT], check=True)
    unit.unlink()
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
if application.exists():
    shutil.rmtree(application)
print('Removed MyCount application, service, GeoIP schedule, and Caddy site.')
print('Preserved databases, credentials, Linux accounts, Caddy, cron, and router mappings.')
PY
