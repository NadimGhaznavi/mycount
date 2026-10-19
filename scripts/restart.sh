#!/usr/bin/env bash
# Apply production network settings and restart MyCount services.
set -euo pipefail
if [[ ${1:-} == --help && $# == 1 ]]; then
    printf 'Usage: sudo scripts/restart.sh\nApply conf/mycount.json, reload Caddy, and restart MyCount services.\n'
    exit 0
fi
[[ $# == 0 && $EUID == 0 ]] || { printf 'Run scripts/restart.sh as root, without arguments.\n' >&2; exit 1; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
install_dir=$(python3 -B - <<'PY'
from mycount.constants.DMyCount import DMyCount
print(DMyCount.BASE_DIR)
PY
)
cd -- "$install_dir"
.venv/bin/python -B - <<'PY'
import subprocess
from pathlib import Path
from mycount.constants.DControl import DControl
from mycount.constants.DMyCount import DMyCount
from mycount.constants.DRouterMappings import DRouterMappings
from mycount.interface.Configuration import Configuration

Configuration.read(Path(DMyCount.BASE_DIR) / DMyCount.CONFIG_FILE, DMyCount.CMDB_NETWORK)
subprocess.run(['bash', 'scripts/install-caddy.sh'], check=True)
subprocess.run(['systemctl', 'restart', DMyCount.SERVICE_UNIT, DControl.SERVICE_UNIT,
                DRouterMappings.SERVICE_UNIT], check=True)
print('Applied production network configuration and restarted MyCount.')
PY
