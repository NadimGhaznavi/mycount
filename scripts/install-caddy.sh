#!/usr/bin/env bash
# Configure the existing Caddy service and forward the public ports.
set -euo pipefail
umask 022
[[ $# == 0 && $EUID == 0 ]] || { printf 'Run scripts/install-caddy.sh as root, without arguments.\n' >&2; exit 1; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
command -v caddy >/dev/null || apt-get install -y caddy
command -v upnpc >/dev/null || apt-get install -y miniupnpc
python3 -B - <<'PY'
from pathlib import Path
import shutil
import subprocess
from tempfile import NamedTemporaryFile

from mycount.constants.DCaddy import DCaddy
from mycount.constants.DMyCount import DMyCount

config = Path(DCaddy.CONFIG)
site = Path(DCaddy.SITE_CONFIG)
original = config.read_text()
rendered = Path('caddy/mycount.caddy').read_text()
for name, value in {
    'DOMAIN': DCaddy.HOSTNAME, 'UPSTREAM': f'{DMyCount.HOST}:{DMyCount.PORT}',
    'COLLECTION_PATH': DMyCount.COLLECTION_PATH, 'HEALTH_PATH': DMyCount.HEALTH_PATH,
    'VISITOR_HEADER': DCaddy.VISITOR_HEADER,
}.items():
    rendered = rendered.replace(f'@{name}@', str(value))
directive = f'import {site}'
base = '\n'.join(line for line in original.splitlines() if line.strip() != directive)
# Keep relative imports anchored in the existing configuration directory.
with NamedTemporaryFile(mode='w', prefix='.mycount-', suffix='.Caddyfile', dir=config.parent) as candidate:
    candidate.write(base + '\n' + rendered)
    candidate.flush()
    subprocess.run(['caddy', 'validate', '--config', candidate.name, '--adapter', 'caddyfile'], check=True)
backup = config.with_name(config.name + '.before-mycount')
if not backup.exists():
    shutil.copy2(config, backup)
previous_site = site.read_bytes() if site.exists() else None
site.write_text(rendered)
site.chmod(0o644)
config.write_text(base + '\n' + directive + '\n')
try:
    subprocess.run(['systemctl', 'enable', '--now', DCaddy.SERVICE], check=True)
    subprocess.run(['systemctl', 'reload', DCaddy.SERVICE], check=True)
except subprocess.CalledProcessError:
    config.write_text(original)
    if previous_site is None:
        site.unlink()
    else:
        site.write_bytes(previous_site)
    raise
for port in (DCaddy.HTTP_PORT, DMyCount.HTTPS_PORT):
    subprocess.run(['upnpc', '-a', DCaddy.LAN_HOST, str(port), str(port), 'TCP'], check=True)
print(f'Configured https://{DCaddy.HOSTNAME}{DMyCount.COLLECTION_PATH}; check certificate issuance in the Caddy journal.')
PY
