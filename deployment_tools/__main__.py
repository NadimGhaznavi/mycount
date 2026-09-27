"""Update or verify dependency constants from a project rules file."""
import argparse
from pathlib import Path
from deployment_tools.DependencyGenerator import DependencyGenerator


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--rules', required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        current = DependencyGenerator(args.root, args.rules).update(check=args.check)
    except (ValueError, OSError, SyntaxError) as error:
        parser.exit(2, f'{error}\n')
    if not current:
        parser.exit(1, 'Dependency constants are stale; regenerate and commit them.\n')
    print('Dependency constants are current.' if args.check else 'Dependency constants generated.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
