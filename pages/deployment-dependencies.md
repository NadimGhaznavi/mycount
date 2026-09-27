---
title: Deployment dependencies
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

## Design

Separate dependency discovery, impact analysis, release decisions, and deployment
execution. Shared files can affect multiple targets; upgrades combine release
flags across skipped versions. Successful-release metadata advances after the
selected stages succeed. Filesystem/setup impact currently selects both services.

| Component | Responsibility |
| --- | --- |
| `deployment_tools/` | Portable scanner, graph validation, impact analysis, release metadata, file copying |
| `deployment/rules.json` | MyCount scan paths, target roots, exclusions, extra dependencies |
| `deployment/DDeployment.py.in` | MyCount constants output template |
| `DeploymentConfiguration.py` | MyCount paths, version normalization, copying and setup policy |
| Release/upgrade scripts | Call the helpers and perform project-specific system operations |

Copy `deployment_tools/` unchanged into another project. It uses only Python's
standard library and contains no MyCount imports, paths, or service names.
Supply that project's rules, output template, and `DeploymentConfig`; keep its
service/database/setup actions outside the reusable package.

## Maintenance

```sh
python3 -B scripts/update-deployment-dependencies.py
python3 -B scripts/update-deployment-dependencies.py --check
```

Commit the generated `mycount/constants/DDeployment.py` alongside source/rule
changes. Release preparation requires `--check` before modifying release state.
The portable entry point is `python3 -B -m deployment_tools --rules <rules.json>`;
add `--check` for a read-only check (exit 1 means stale, exit 2 means invalid).

The scanner reads Python imports/package initializers, quoted `PY*` shell
heredocs, and literal Jinja references within configured template roots. Explicit
`extra` rules cover shell calls, service entry points, and dynamically loaded
files. Missing imports/files, cycles, and unreachable artifacts fail generation.
Dynamic imports/templates require explicit rules; this is static analysis, not
execution of project code. Sorted output makes regeneration deterministic.

See [Release management]({% link pages/releases.md %}) and
[Upgrading]({% link pages/upgrading.md %}) for operational details.
