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
targets=(filesystem listener report-server)
units=("${settings[@]:3}")
full_setup=true
if [[ $upgrade == true ]]; then
    flags=$(python3 -B - "$install_dir" <<'PYFLAGS'
from pathlib import Path
import sys
from mycount.activity.ReleaseDeployment import ReleaseDeployment
from mycount.constants.DDeployment import DDeployment
from mycount.constants.DMyCount import DMyCount
from mycount.interface.ReleaseFiles import ReleaseFiles

installation = Path(sys.argv[1])
previous = ReleaseFiles(Path.cwd()).installed_version(installation)
targets = ReleaseDeployment(ReleaseFiles(Path.cwd())).upgrade_targets(previous, DMyCount.VERSION)
# Preserve the last successful version before application files are replaced.
(installation / DDeployment.VERSION_MARKER).write_text(previous + '\n')
for target in sorted(targets):
    print(target)
PYFLAGS
)
    targets=()
    units=()
    full_setup=false
    while IFS= read -r target; do
        [[ -n $target ]] || continue
        targets+=("$target")
        case "$target" in
            listener) units+=("${settings[3]}") ;;
            report-server) units+=("${settings[4]}") ;;
            filesystem) full_setup=true ;;
        esac
    done <<< "$flags"
    printf 'Upgrade targets: %s\n' "${flags:-none}"
fi

stop_services() {
    for unit in "${units[@]}"; do
        if [[ -e /etc/systemd/system/$unit ]]; then
            systemctl stop "$unit"
        fi
    done
}

install_dependencies() {
    if [[ ! -x $install_dir/.venv/bin/python ]]; then
        python3 -m venv "$install_dir/.venv"
    fi
    "$install_dir/.venv/bin/python" -m pip install -r requirements.txt
}

copy_selected_files() {
    printf 'Copying files for selected deployment targets...\n'
    python3 -B - "$install_dir" "${targets[@]}" <<'PYFILES'
from pathlib import Path
import sys
from mycount.constants.DDeployment import DDeployment
from mycount.interface.DeploymentFiles import DeploymentFiles

files = DeploymentFiles(Path.cwd(), Path(sys.argv[1]))
targets = frozenset(sys.argv[2:])
files.copy_application(targets)
if DDeployment.FILESYSTEM in targets:
    files.copy_setup()
PYFILES
}

apply_schemas() {
    printf 'Applying database schemas...\n'
"$install_dir/.venv/bin/python" -B - <<'PY'
import logging
import os
from pathlib import Path
from mycount.activity.GeoIpSchema import GeoIpSchema
from mycount.activity.VisitorSchema import VisitorSchema
from mycount.constants.DMyCount import DMyCount
from mycount.interface.DatabaseEnvironment import DatabaseEnvironment
from mycount.interface.DbMgr import DbMgr
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
os.environ.update(DatabaseEnvironment.read(Path(DMyCount.DATABASE_ENV)))
db = DbMgr()
try:
    VisitorSchema(db).apply()
    GeoIpSchema(db).apply()
finally:
    db.close()
PY
}

render_definitions() {
    if [[ $full_setup == true || " ${units[*]} " == *" ${settings[4]} "* ]]; then
        install -d -m 755 -o "${settings[2]}" -g "${settings[2]}" -- "$install_dir/pages/marketing"
    fi
python3 -B - "$checkout" "$full_setup" "${units[@]}" <<'PY'
from pathlib import Path
import sys
from mycount.constants.DGeoIp import DGeoIp
from mycount.constants.DMyCount import DMyCount
from mycount.constants.DControl import DControl
for name in sys.argv[3:]:
    source = Path(sys.argv[1]) / 'systemd' / name
    unit = source.read_text().replace('@APP@', DMyCount.BASE_DIR)
    unit = unit.replace('@DATABASE_ENV@', DMyCount.DATABASE_ENV).replace('@USER@', DMyCount.SERVICE_USER)
    target = Path('/etc/systemd/system', name)
    if not target.exists() or target.read_text() != unit:
        target.write_text(unit)
if sys.argv[2] == 'true':
    command = f'{DMyCount.BASE_DIR}/scripts/update-geoip.sh'
    Path(DGeoIp.CRON_FILE).write_text(
        'SHELL=/bin/bash\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n'
        f'{DGeoIp.CRON_SCHEDULE} root {command}\n')
    Path(DGeoIp.CRON_FILE).chmod(0o644)
PY
}

start_services() {
    printf 'Validating and starting selected MyCount services...\n'
    for unit in "${units[@]}"; do
        systemd-analyze verify "/etc/systemd/system/$unit"
    done
    systemctl daemon-reload
    for unit in "${units[@]}"; do
        systemctl enable --now "$unit"
    done
}

check_health() {
"$install_dir/.venv/bin/python" -B - "${units[@]}" <<'PY'
import sys
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
    if unit not in sys.argv[1:]:
        continue
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
}

complete_deployment() {
    python3 -B - "$install_dir" <<'PYCOMPLETE'
from pathlib import Path
import sys
from mycount.constants.DMyCount import DMyCount
from mycount.interface.DeploymentFiles import DeploymentFiles

DeploymentFiles(Path.cwd(), Path(sys.argv[1])).complete(DMyCount.VERSION)
PYCOMPLETE
}

# Keep the stage selection here so each impact flag has an explicit workflow.
if [[ ${#targets[@]} -gt 0 ]]; then
    stop_services
    if [[ $full_setup == true ]]; then
        install_dependencies
    fi
    copy_selected_files
    if [[ $full_setup == true ]]; then
        apply_schemas
    fi
    if [[ $upgrade == false ]]; then
        printf 'Downloading and importing GeoIP datasets; this may take several minutes...\n'
        "$install_dir/scripts/update-geoip.sh"
    fi
    render_definitions
    if [[ $full_setup == true ]]; then
        systemctl enable --now cron.service
    fi
    if [[ ${#units[@]} -gt 0 ]]; then
        start_services
        check_health
    fi
    if [[ $full_setup == true ]]; then
        printf 'Configuring Caddy and router forwarding...\n'
        "$checkout/scripts/install-caddy.sh"
    fi
else
    printf 'No deployment targets affected; recording the release only.\n'
fi
complete_deployment
printf 'MyCount deployment completed successfully.\n'
