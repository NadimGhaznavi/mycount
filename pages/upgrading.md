---
title: Upgrading
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

From the updated source checkout, run:

```sh
sudo scripts/upgrade.sh
```

Run [installation]({% link pages/installation.md %}) first on a new machine.
The upgrade script deploys the current checkout; it does not fetch or merge Git
changes. Use a checkout separate from `/opt/prod/mycount`.

The upgrade validates the retained database credentials, stops the collector,
updates Python dependencies and application files, applies database schema
updates, refreshes the service and cron definitions, and starts the collector.
It checks local health before running Caddy and router setup. This also deploys
changes to `DMyCount.ORIGINS`.

Existing visits, database credentials, database and Linux accounts, and GeoIP
data are preserved. No MariaDB administrator access is needed. The lengthy
GeoIP download/import is skipped; the weekly job continues to refresh it.
For an immediate refresh, run:

```sh
sudo /opt/prod/mycount/scripts/update-geoip.sh
```

Upgrading needs root access and network access for dependencies and router setup.
Collection is interrupted while deployment runs. A failure can leave the service
stopped or partially updated; correct the reported error and rerun the upgrade.
There is no automatic application or database rollback.

Afterward, verify `https://count.osoyalce.com/health` from outside the LAN and
expect HTTP 204. Changes to browser pages or their Jekyll configuration require
a separate website rebuild and publication.
