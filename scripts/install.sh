#!/usr/bin/env bash
# Provision the local accounts and database, then deploy MyCount.
set -euo pipefail
umask 022

if [[ ${1:-} == --help ]]; then
    printf 'Usage: sudo scripts/install.sh\nInstall MyCount, initialize its database, and configure HTTPS and router forwarding.\n'
    exit 0
fi
[[ $# == 0 && $EUID == 0 ]] || { printf 'Run scripts/install.sh as root, without arguments.\n' >&2; exit 1; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
command -v mariadb >/dev/null
command -v systemctl >/dev/null
command -v systemd-analyze >/dev/null
command -v cron >/dev/null
command -v runuser >/dev/null
python3 -B - <<'PY'
import sys
import venv
import ensurepip
if sys.version_info < (3, 11):
    raise SystemExit('MyCount requires Python 3.11 or later.')
PY
mariadb --protocol=socket --user=root --batch --skip-column-names -e 'SELECT 1' >/dev/null

mapfile -t settings < <(python3 -B - <<'PY'
from mycount.constants.DMyCount import DMyCount
print(DMyCount.BASE_DIR)
print(DMyCount.SERVICE_USER)
PY
)
install_dir=${settings[0]}
account=${settings[1]}
getent group "$account" >/dev/null || groupadd --system "$account"
getent passwd "$account" >/dev/null || useradd --system --gid "$account" \
    --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin "$account"
install -d -m 755 -- "$install_dir"

# Credentials are never sourced as shell code or passed in command arguments.
python3 -B - <<'PY'
import os
from pathlib import Path
import re
import secrets
import subprocess
from mycount.constants.DDbMgr import DDbMgr
from mycount.constants.DMyCount import DMyCount
from mycount.interface.DatabaseEnvironment import DatabaseEnvironment

path = Path(DMyCount.DATABASE_ENV)
expected = {'DB_HOST': 'localhost', 'DB_PORT': str(DDbMgr.PORT),
            'DB_NAME': DMyCount.DATABASE_NAME, 'DB_USER': DMyCount.DATABASE_USER}
if path.is_symlink():
    raise SystemExit('Credentials must not be a symbolic link.')
if path.exists():
    stat = path.stat()
    if stat.st_uid != 0 or stat.st_mode & 0o777 != 0o600:
        raise SystemExit('Existing credentials must be root-owned with mode 600.')
    values = DatabaseEnvironment.read(path)
    if any(values[key] != value for key, value in expected.items()):
        raise SystemExit('Existing credentials do not match MyCount.')
    password = values['DB_PASSWORD']
    if re.fullmatch('[a-f0-9]{64}', password) is None:
        raise SystemExit('Existing credentials do not match the generated password format.')
else:
    password = secrets.token_hex(32)
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        for key, value in {**expected, 'DB_PASSWORD': password}.items():
            stream.write(f'{key}={value}\n')

database, user = DMyCount.DATABASE_NAME, DMyCount.DATABASE_USER
sql = (f'CREATE DATABASE IF NOT EXISTS `{database}`;\n'
       f"CREATE USER IF NOT EXISTS '{user}'@'localhost' IDENTIFIED BY '{password}';\n"
       f"GRANT ALL ON `{database}`.* TO '{user}'@'localhost';\n")
subprocess.run(['mariadb', '--protocol=socket', '--user=root'], input=sql, text=True, check=True)
subprocess.run(['mariadb', '--no-defaults', '--protocol=socket', '--user=' + user,
                '--database=' + database, '-e', 'SELECT 1'],
               env={**os.environ, 'MYSQL_PWD': password}, stdout=subprocess.DEVNULL, check=True)
PY
exec scripts/install-services.sh
