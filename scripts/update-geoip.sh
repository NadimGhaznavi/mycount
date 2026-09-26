#!/usr/bin/env bash
# Run from either the installed tree or a prepared checkout.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
exec .venv/bin/python -B -m mycount.activity.UpdateGeoIp
