#!/usr/bin/env bash
# Remove MyCount's TCP port mappings and UDP mappings with the same destination.
set -euo pipefail

if [[ ${1:-} == --help && $# == 1 ]]; then
    printf 'Usage: scripts/clear-upnpc-routes.sh\nRemove MyCount TCP port 80/443 mappings and UDP mappings on those ports with the same destination host and internal port.\nRequires upnpc (miniupnpc); root privileges are not needed.\n'
    exit 0
fi
[[ $# == 0 ]] || { printf 'Usage: scripts/clear-upnpc-routes.sh\n' >&2; exit 1; }
command -v upnpc >/dev/null || { printf 'Install miniupnpc to provide the upnpc command.\n' >&2; exit 1; }

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python3 -B - <<'PY'
from mycount.constants.DCaddy import DCaddy
from mycount.constants.DMyCount import DMyCount
from mycount.interface.RouterMappings import RouterMappings

ports = (DCaddy.HTTP_PORT, DMyCount.HTTPS_PORT)
RouterMappings().clear(ports)
print(f'Cleared MyCount TCP ports {ports[0]}, {ports[1]} and matching UDP mappings.')
PY
