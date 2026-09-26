---
title: Installation
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

Run the installer as root from your cloned checkout:

```sh
sudo scripts/install.sh
```

The machine needs Python 3.11 or later with virtual-environment support,
MariaDB server and client, systemd, and cron. MariaDB must be running with
root administrative access through its local socket. Installation needs
network access for Python dependencies and the initial GeoIP download.

The installer creates the `mycount` database and database account, a Linux
service account, and `/etc/mycount/database.env` with root-only permissions.
It reuses existing credentials without resetting the database password.
It copies the application to `/opt/prod/mycount`, creates its `.venv`, applies
the schema, imports GeoIP data, and installs and starts `mycount-server.service`.

Runtime defaults are in `mycount/constants/DMyCount.py`. The collector listens
on `127.0.0.1:36666`. Connecting `count.osoyalce.com` to it through HTTPS and
configuring trusted visitor-IP forwarding remain deployment work. The
separate mydynip service provides dynamic-IP updates and is not modified by
this installer.

## GeoIP updates

MyCount uses the free ipapi.is
[IPv4](https://github.com/ipapi-is/ipapi/blob/main/databases/geolocationDatabaseIPv4.csv.zip)
and [IPv6](https://github.com/ipapi-is/ipapi/blob/main/databases/geolocationDatabaseIPv6.csv.zip)
datasets. Public reference data is imported into MariaDB for local lookups.
The archives are temporary and removed after processing.

Installation creates `/etc/cron.d/mycount-geoip`. Its default schedule is
Sunday at 03:17 in the machine's timezone. The download URLs and schedule are
defined in `mycount/constants/DGeoIp.py`.

Each refresh stages both address families before replacing the active data.
A failed download or import leaves the previous dataset available. No service
restart is needed. Allow disk space for both the active and replacement data
and the temporary downloads.

To refresh manually after installation:

```sh
sudo /opt/prod/mycount/scripts/update-geoip.sh
```
