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
The automatic package installation uses apt on Debian/Ubuntu systems. Run
deployment from a checkout separate from `/opt/prod/mycount`.

The installer creates the `mycount` database and database account, a Linux
service account, and `/etc/mycount/database.env` with root-only permissions.
It reuses existing credentials without resetting the database password.
It copies the application to `/opt/prod/mycount`, creates its `.venv`, applies
the schema, imports GeoIP data, and installs and starts `mycount-server.service`
and `mycount-control.service`. It checks both local health endpoints before
configuring Caddy. Upgrades stop both services before updating dependencies
and code; an installation failure can leave them stopped. Correct the reported error and
rerun the installer. Installation is not a transactional rollback mechanism.

See [Uninstall]({% link pages/uninstall.md %}) for removal that preserves data.
For an existing installation, use the [upgrade script]({% link pages/upgrading.md %})
to deploy changes without repeating the GeoIP import.

Runtime defaults are in `mycount/constants/DMyCount.py`. The collector listens
on `127.0.0.1:36666`. Caddy serves public HTTPS on port `443`, routing `/count`
and `/health` to the collector and forwarding visitor addresses. The
separate mydynip service provides dynamic-IP updates and is not modified by
this installer.

The [Control server]({% link pages/control-server.md %}) displays a dark orange
MyCount banner at `http://<server>:61777/`.

## HTTPS and router forwarding

The installer runs `scripts/install-caddy.sh`, installing Caddy and miniupnpc
with apt if missing. It preserves the existing Caddy sites, adds a MyCount
import, validates the combined configuration, and reloads Caddy. The original
Caddyfile is saved as `/etc/caddy/Caddyfile.before-mycount` on the first run.
Access logging is not enabled for the collector site.

Review `mycount/constants/DCaddy.py` before installation. `LAN_HOST` is the
machine's LAN IPv4 address; reserve that address in DHCP. The public hostname
must resolve to this router's public address. UPnP maps TCP ports 80 and
443 to this machine. Port 80 supports automatic public certificate
issuance and renewal; keep it reachable. Existing LAN-only site restrictions
remain in place. After a router reset, rerun the Caddy setup to restore mappings.

The imported `/etc/caddy/mycount.caddy` declares `https://count.osoyalce.com`;
Caddy automatically listens on 443 and obtains and renews its certificate.
An existing `:80` block serves HTTP only. Keep the import outside that block
so the public collector has its own hostname and routes. The collector's
internal port 36666 does not need router forwarding. Remove any old 36666
forwarding rule from the router when migrating from the previous setup.

For an existing installation, configure HTTPS from the checkout with:

```sh
sudo scripts/install-caddy.sh
```

Deploy the updated collector code as well to accept `/count` and forwarded
visitor addresses, and publish the updated client endpoint configuration.
Check `journalctl -u caddy` for certificate issuance, then request
`https://count.osoyalce.com/health` from outside the LAN; expect HTTP 204.

### Caddy configuration

The setup script generates `/etc/caddy/mycount.caddy` with the following
configuration using the default hostname and collector settings:

```caddyfile
https://count.osoyalce.com {
    @collector path /count /health
    handle @collector {
        reverse_proxy 127.0.0.1:36666 {
            header_up X-MyCount-Client-IP {http.request.remote.host}
        }
    }
    handle {
        respond 404
    }
}
```

The `/count` path is passed unchanged to the collector. The proxy supplies
the visitor address for geolocation. Other paths on this hostname return 404.
The browser client endpoint is `https://count.osoyalce.com/count`.

Keep your existing site blocks in `/etc/caddy/Caddyfile`. Add the import once,
outside all site blocks. For the existing LAN-only site, the complete layout is:

```caddyfile
:80 {
    encode zstd gzip

    @outside_lan not remote_ip 192.168.0.0/24 127.0.0.0/8 ::1
    abort @outside_lan

    handle /api {
        reverse_proxy 127.0.0.1:8000
    }

    @account_pages path /login /signup /dashboard /pool /pool/new
    handle @account_pages {
        reverse_proxy 127.0.0.1:8000
    }

    handle {
        root * /opt/xmr/web/static
        file_server
    }
}

import /etc/caddy/mycount.caddy
```

The LAN restriction belongs to the existing HTTP site. The imported HTTPS
site allows public collection on port 443. Caddy obtains and renews its
certificate automatically; no separate certificate files or `tls` directive
are required for this configuration.

After manual configuration changes, validate the complete Caddyfile and
reload only if validation succeeds:

```sh
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile &&
sudo systemctl reload caddy
```

With DNS pointing to the router and TCP ports 80 and 443 forwarded to this
machine, verify from outside the LAN:

```sh
curl -i https://count.osoyalce.com/health
```

Expect HTTP 204. This checks HTTPS and proxy connectivity; use the
[browser client verification]({% link pages/client.md %}) to check collection.

## GeoIP updates

GeoIP imports retain country names, latitude, longitude, ZIP/postal code, and timezone
alongside country codes, region, and city. New visits copy the available values.
Coordinates, ZIP/postal code, and timezone added to existing ranges remain
empty until the next scheduled or manual GeoIP refresh; those fields are not
backfilled on historical visits.

Upgrades add nullable `country_name` columns to reference ranges and visits,
backfill missing names from recognized ISO country codes using `pycountry`,
and drop the obsolete `continent` columns. Backfills scan primary keys in
batches of 1,000 rows, log progress, and commit each batch separately. Retrying
an interrupted upgrade preserves completed names and fills remaining gaps. Unknown codes remain unnamed.
New imports retain the CSV country name; later refreshes do not rewrite names
on existing visits.

MyCount uses the free ipapi.is
[IPv4](https://github.com/ipapi-is/ipapi/blob/main/databases/geolocationDatabaseIPv4.csv.zip)
and [IPv6](https://github.com/ipapi-is/ipapi/blob/main/databases/geolocationDatabaseIPv6.csv.zip)
datasets. Public reference data is imported into MariaDB for local lookups.
The archives are temporary and removed after processing.
The initial download and import can take several minutes after Python dependency
installation. The installer reports each stage; GeoIP imports report row counts
about every ten seconds while batches complete, followed by publication of both
datasets. Download stages report their start and completion through the transition
to importing.

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
