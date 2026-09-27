#!/usr/bin/env python3
"""Generate MyCount's deployment constants from its source and project rules."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from deployment_tools.DependencyGenerator import DependencyGenerator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        current = DependencyGenerator(ROOT, 'deployment/rules.json').update(check=args.check)
    except (OSError, ValueError, SyntaxError) as error:
        parser.exit(2, f'{error}\n')
    if not current:
        parser.exit(1, 'DDeployment.py is stale; run scripts/update-deployment-dependencies.py and commit it.\n')
    print('Deployment dependencies are current.' if args.check else 'Updated DDeployment.py.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
