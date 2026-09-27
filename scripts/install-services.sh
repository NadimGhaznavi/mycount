#!/usr/bin/env bash
# Deploy the application after provisioning and prepare its weekly refresh.
set -euo pipefail
umask 022
[[ $EUID == 0 && ( $# == 0 || ( $# == 1 && $1 == --upgrade ) ) ]] || { printf 'Usage: sudo scripts/install-services.sh [--upgrade]\n' >&2; exit 1; }
upgrade=false
if [[ ${1:-} == --upgrade ]]; then
    upgrade=true
fi
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
checkout=$PWD
settings_output=$(python3 -B - <<'PY'
from mycount.constants.DMyCount import DMyCount
from mycount.constants.DControl import DControl
print(DMyCount.BASE_DIR)
print(DMyCount.DATABASE_ENV)
print(DMyCount.SERVICE_USER)
print(DMyCount.SERVICE_UNIT)
print(DControl.SERVICE_UNIT)
PY
)
mapfile -t settings <<< "$settings_output"
install_dir=${settings[0]}
[[ -d $install_dir && -f ${settings[1]} ]] || { printf 'Run install.sh first.\n' >&2; exit 1; }
getent passwd "${settings[2]}" >/dev/null
[[ $checkout != "$install_dir" ]] || { printf 'Run deployment from a separate checkout.\n' >&2; exit 1; }
# Validate retained credentials before stopping a working deployment.
python3 -B - <<'PY'
from pathlib import Path
from mycount.constants.DMyCount import DMyCount
from mycount.interface.DatabaseEnvironment import DatabaseEnvironment

path = Path(DMyCount.DATABASE_ENV)
if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o777 != 0o600:
    raise SystemExit('Credentials must be a root-owned regular file with mode 600.')
values = DatabaseEnvironment.read(path)
if values['DB_NAME'] != DMyCount.DATABASE_NAME or values['DB_USER'] != DMyCount.DATABASE_USER:
    raise SystemExit('Credentials do not belong to MyCount; run install.sh first.')
PY
for unit in "${settings[@]:3}"; do
    if [[ -e /etc/systemd/system/$unit ]]; then
        systemctl stop "$unit"
    fi
done
if [[ ! -x $install_dir/.venv/bin/python ]]; then
    python3 -m venv "$install_dir/.venv"
fi
"$install_dir/.venv/bin/python" -m pip install -r requirements.txt
printf 'Copying MyCount application files...\n'
python3 -B - "$install_dir" <<'PY'
from pathlib import Path
import shutil
import sys
target = Path(sys.argv[1])
shutil.copytree('mycount', target / 'mycount', dirs_exist_ok=True,
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
shutil.copy2('requirements.txt', target / 'requirements.txt')
(target / 'scripts').mkdir(exist_ok=True)
shutil.copy2('scripts/update-geoip.sh', target / 'scripts/update-geoip.sh')
shutil.copy2('scripts/uninstall.sh', target / 'scripts/uninstall.sh')
PY
cd -- "$install_dir"
printf 'Applying database schemas...\n'
.venv/bin/python -B - <<'PY'
import os
from pathlib import Path
from mycount.activity.GeoIpSchema import GeoIpSchema
from mycount.activity.VisitorSchema import VisitorSchema
from mycount.constants.DMyCount import DMyCount
from mycount.interface.DatabaseEnvironment import DatabaseEnvironment
from mycount.interface.DbMgr import DbMgr
os.environ.update(DatabaseEnvironment.read(Path(DMyCount.DATABASE_ENV)))
db = DbMgr()
try:
    VisitorSchema(db).apply()
    GeoIpSchema(db).apply()
finally:
    db.close()
PY
if [[ $upgrade == false ]]; then
    printf 'Downloading and importing GeoIP datasets; this may take several minutes...\n'
    scripts/update-geoip.sh
else
    printf 'Keeping existing GeoIP data; weekly refresh remains scheduled.\n'
fi

# Render installation paths from the same constants as the application.
.venv/bin/python -B - "$checkout" <<'PY'
from pathlib import Path
import sys
from mycount.constants.DGeoIp import DGeoIp
from mycount.constants.DMyCount import DMyCount
from mycount.constants.DControl import DControl
for name in (DMyCount.SERVICE_UNIT, DControl.SERVICE_UNIT):
    source = Path(sys.argv[1]) / 'systemd' / name
    unit = source.read_text().replace('@APP@', DMyCount.BASE_DIR)
    unit = unit.replace('@DATABASE_ENV@', DMyCount.DATABASE_ENV).replace('@USER@', DMyCount.SERVICE_USER)
    Path('/etc/systemd/system', name).write_text(unit)
command = f'{DMyCount.BASE_DIR}/scripts/update-geoip.sh'
Path(DGeoIp.CRON_FILE).write_text(
    'SHELL=/bin/bash\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n'
    f'{DGeoIp.CRON_SCHEDULE} root {command}\n')
Path(DGeoIp.CRON_FILE).chmod(0o644)
PY
printf 'Validating and starting MyCount services...\n'
for unit in "${settings[@]:3}"; do
    systemd-analyze verify "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl enable --now cron.service
for unit in "${settings[@]:3}"; do
    systemctl enable --now "$unit"
done
.venv/bin/python -B - <<'PY'
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
from mycount.constants.DMyCount import DMyCount

from mycount.constants.DControl import DControl

opener = build_opener(ProxyHandler({}))
for port, expected, unit in (
    (DMyCount.PORT, 204, DMyCount.SERVICE_UNIT),
    (DControl.PORT, 200, DControl.SERVICE_UNIT),
):
    url = f'http://127.0.0.1:{port}/health'
    for attempt in range(30):
        try:
            with opener.open(url, timeout=1) as response:
                if response.status == expected:
                    break
        except (URLError, TimeoutError):
            pass
        time.sleep(1)
    else:
        raise SystemExit('Health check failed; inspect journalctl -u ' + unit)
print(f'MyCount Control: http://<server>:{DControl.PORT}/')
PY
printf 'Configuring Caddy and router forwarding...\n'
"$checkout/scripts/install-caddy.sh"
printf 'Installed %s and %s and scheduled weekly GeoIP updates.\n' "${settings[3]}" "${settings[4]}"
