---
title: Uninstall
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

Run from your checkout:

```sh
sudo scripts/uninstall.sh
```

The installer also copies the uninstaller into the deployed application:

```sh
sudo /opt/prod/mycount/scripts/uninstall.sh
```

The script removes MyCount's Caddy import and site file, disables and stops
`mycount-server.service` and `mycount-control.service`, removes both units and
any legacy MyCount GeoIP schedule, and
deletes the application files under `/opt/prod/mycount`, preserving uploaded
PNGs in `pages/marketing` when that folder exists. It validates the remaining Caddy configuration
before changing it and reloads Caddy if active. Other Caddy sites are preserved;
the old Caddyfile backup is not restored over newer configuration changes.
Repeated runs from the checkout are safe.

The database and its MariaDB account, `/etc/mycount/database.env`, and the Linux
service account are retained for reinstallation. Caddy, MariaDB, cron, Python
packages installed through apt, the Caddyfile backup, and router port mappings
are also retained because they may be shared. Remove router mappings manually
only when no other site uses them. The separate mydynip service is untouched.

For a legacy deployment, finish any in-progress GeoIP refresh before removal.
The external BMGeoIP service and its data are untouched.
The directory-removal guard accepts only `/opt/prod/mycount`; deployments using
a customized application directory require manual removal of that directory.

To restore the application with the retained data, follow the
[installation guide]({% link pages/installation.md %}).
