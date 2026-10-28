#!/usr/bin/env bash
# Start or stop MyCount services sequentially.
set -euo pipefail
if [[ $# == 1 && $1 == --help ]]; then
    printf 'Usage: sudo scripts/services.sh {start|stop}\nStart the collector, Control, and router worker in order; stop them in reverse order.\n'
    exit 0
fi
[[ $# == 1 && ( $1 == start || $1 == stop ) ]] || { printf 'Usage: sudo scripts/services.sh {start|stop}\n' >&2; exit 1; }
[[ $EUID == 0 ]] || { printf 'Run scripts/services.sh as root.\n' >&2; exit 1; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python3 -B - "$1" <<'PY'
import subprocess
import sys

from mycount.constants.DControl import DControl
from mycount.constants.DMyCount import DMyCount
from mycount.constants.DRouterMappings import DRouterMappings

action = sys.argv[1]
units = (DMyCount.SERVICE_UNIT, DControl.SERVICE_UNIT, DRouterMappings.SERVICE_UNIT)
if action == 'stop':
    units = tuple(reversed(units))
for unit in units:
    print(f'{action} {unit}', flush=True)
    subprocess.run(['systemctl', action, unit], check=True)
PY
