---
title: Upgrading
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

From a released checkout prepared by `scripts/new-release.sh`, run:

```sh
sudo scripts/upgrade.sh
```

Run [installation]({% link pages/installation.md %}) first on a new machine.
The upgrade script deploys the prepared release; it does not fetch or merge Git
changes. Use a checkout separate from `/opt/prod/mycount`. Unreleased changes to
deployment files are rejected before any service is stopped.

The upgrade validates retained credentials and reads `deployment/releases.json`.
It combines the recorded target flags for every release after the last successful
installed version, so skipping a release does not skip required work.

- Report-server changes stop, update, start, and health-check only `mycount-control`.
- Listener changes select `mycount-server` instead. Both flags select both services.
- Filesystem/setup changes run the full workflow: both services, Python dependencies,
  database schemas, service/cron definitions, and Caddy/router setup.
- Releases with no deployment impact update the release files/version without restarting services.

The deployment script separates file copying, dependency installation, schema
setup, unit rendering, service startup, health checks, and completion into named
stages. Service-only upgrades copy application artifacts belonging to the selected
targets, including their shared dependencies. Obsolete files are removed only for
those targets, using the installed release manifest. Requirements and setup scripts
are copied only during filesystem/setup deployments. No-impact upgrades skip
application copying, unit rendering, health checks, and setup entirely after preflight.

Unchanged application modules and unit files are not rewritten. The automatic version-number
bump is excluded from impact calculations; other changes to `DMyCount.py` still
affect its dependents. Release inputs are hash-checked before deployment, but the
dependency analysis happens during release preparation.

`/opt/prod/mycount/.deployment-version` records the last successful deployment.
For an existing installation without it, the installed `DMyCount.VERSION` seeds
the marker before files are replaced. A failed upgrade retains the previous marker
so a retry selects the same required work. The installed release manifest is also
published only after the selected stages succeed. Unknown versions or incomplete release
history stop the upgrade rather than guessing restart flags.

Existing visits, database credentials, database and Linux accounts, and GeoIP
data are preserved. No MariaDB administrator access is needed. The lengthy
GeoIP download/import is skipped; the weekly job continues to refresh it.
For an immediate refresh, run:

```sh
sudo /opt/prod/mycount/scripts/update-geoip.sh
```

Upgrading needs root access; full setup also needs network access for dependencies
and router setup. Collection continues during report-only upgrades. A failure can leave a service
stopped or partially updated; correct the reported error and rerun the upgrade.
There is no automatic application or database rollback.

Afterward, verify `https://count.osoyalce.com/health` from outside the LAN and
expect HTTP 204. Changes to browser pages or their Jekyll configuration require
a separate website rebuild and publication.
