#!/usr/bin/env bash
# Remove the deployment while preserving data and shared infrastructure.
set -euo pipefail
umask 022
if [[ ${1:-} == --help && $# == 1 ]]; then
    printf 'Usage: sudo scripts/uninstall.sh\nRemove MyCount services, application, TCP port 80/443 mappings, and matching UDP mappings; preserve databases, credentials, and accounts.\n'
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
from mycount.constants.DCities import DCities
from mycount.constants.DMyCount import DMyCount
from mycount.constants.DControl import DControl
from mycount.constants.DMarketing import DMarketing
from mycount.constants.DRouterMappings import DRouterMappings

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
Path(DCities.CRON_FILE).unlink(missing_ok=True)
for name in (DRouterMappings.SERVICE_UNIT, DControl.SERVICE_UNIT, DMyCount.SERVICE_UNIT):
    unit = Path('/etc/systemd/system') / name
    if unit.exists():
        subprocess.run(['systemctl', 'disable', '--now', name], check=True)
        unit.unlink()
subprocess.run(['systemctl', 'daemon-reload'], check=True)
# Run while the deployed script and its imports still exist.
subprocess.run(['bash', 'scripts/clear-upnpc-routes.sh'], check=True)
if application.exists():
    screenshots = application / DMarketing.SCREENSHOT_DIRECTORY
    if screenshots.is_dir() and not screenshots.is_symlink() and not screenshots.parent.is_symlink():
        def remove(path):
            if path.is_symlink() or path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)

        for child in application.iterdir():
            if child == screenshots.parent:
                for page in child.iterdir():
                    if page != screenshots:
                        remove(page)
            else:
                remove(child)
    else:
        shutil.rmtree(application)
print('Removed MyCount application, services, city and legacy GeoIP schedules, Caddy site, and port mappings.')
print('Preserved marketing screenshots, databases, credentials, Linux accounts, Caddy, cron, and unrelated router mappings.')
PY
