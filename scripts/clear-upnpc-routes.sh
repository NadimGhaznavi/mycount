#!/usr/bin/env bash
# Remove MyCount's TCP port mappings and UDP mappings with the same destination.
set -euo pipefail

if [[ ${1:-} == --help && $# == 1 ]]; then
    printf 'Usage: scripts/clear-upnpc-routes.sh\nRemove MyCount configured public HTTP/HTTPS TCP mappings and UDP mappings on those ports with the same destination host and internal port.\nRequires upnpc (miniupnpc); root privileges are not needed.\n'
    exit 0
fi
[[ $# == 0 ]] || { printf 'Usage: scripts/clear-upnpc-routes.sh\n' >&2; exit 1; }
command -v upnpc >/dev/null || { printf 'Install miniupnpc to provide the upnpc command.\n' >&2; exit 1; }

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python3 -B - <<'PY'
from mycount.interface.Network import Network
from mycount.interface.RouterMappings import RouterMappings

ports = (Network.binding("http")[1], Network.binding("https")[1])
RouterMappings().clear(ports)
print(f'Cleared MyCount TCP ports {ports[0]}, {ports[1]} and matching UDP mappings.')
PY
