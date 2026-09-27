#!/usr/bin/env bash
# Update an existing installation from this checkout without reprovisioning it.
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: sudo scripts/upgrade.sh

Deploy this checkout to DMyCount.BASE_DIR and restart the collector.
Preserves databases, credentials, accounts, and existing GeoIP data.
Applies schema updates, checks collector health, and refreshes Caddy and router setup.
Run install.sh first. Does not pull Git changes or require MariaDB administrator access.
HELP
}

if [[ $# == 1 && ( $1 == -h || $1 == --help ) ]]; then
    usage
    exit 0
fi
[[ $# == 0 ]] || { usage >&2; exit 2; }
[[ $EUID == 0 ]] || { printf 'Run scripts/upgrade.sh as root.\n' >&2; exit 1; }
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ -x scripts/install-services.sh ]] || { printf 'Missing executable scripts/install-services.sh.\n' >&2; exit 1; }
scripts/install-services.sh --upgrade
printf 'Upgraded MyCount from %s.\n' "$PWD"
