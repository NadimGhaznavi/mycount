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
`mycount-router.service`, `mycount-server.service`, and `mycount-control.service`,
removes their units and
any legacy MyCount GeoIP schedule, clears MyCount's router port mappings, and
deletes the application files under `/opt/prod/mycount`, preserving uploaded
PNGs in `pages/marketing` when that folder exists. It validates the remaining Caddy configuration
before changing it and reloads Caddy if active. Other Caddy sites are preserved;
the old Caddyfile backup is not restored over newer configuration changes.
Repeated runs from the checkout are safe.

The database and its MariaDB account, `/etc/mycount/database.env`, and the Linux
service account are retained for reinstallation. Caddy, MariaDB, cron, Python
packages installed through apt, and the Caddyfile backup are also retained
because they may be shared. The separate mydynip service is untouched.

The uninstaller invokes `scripts/clear-upnpc-routes.sh` before deleting the
application files. If router cleanup fails, uninstall stops and keeps the
application files so you can retry from the checkout. To run cleanup separately:

```sh
scripts/clear-upnpc-routes.sh
```

This requires `upnpc` from miniupnpc and does not require root. It lists the
mappings before deleting them and checks afterward that the MyCount ports are
clear. UDP mappings on those external ports are also removed when their
destination host and internal port match the corresponding TCP mapping in the
initial listing. Other TCP ports and unmatched UDP mappings are preserved.
TCP ports 80 and 443
are removed regardless of their destination; run this only when those mappings
are no longer needed by other sites, including when uninstalling MyCount.

For a legacy deployment, finish any in-progress GeoIP refresh before removal.
The external BMGeoIP service and its data are untouched.
The directory-removal guard accepts only `/opt/prod/mycount`; deployments using
a customized application directory require manual removal of that directory.

To restore the application with the retained data, follow the
[installation guide]({% link pages/installation.md %}).
