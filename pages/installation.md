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
MariaDB server and client, systemd, cron, and `runuser`. MariaDB must be running with
root administrative access through its local socket. Installation needs
network access for Python dependencies and HTTP access to BMGeoIP at
`geoip.osoyalce.com:54300`.
Scheduled city reference refreshes also need HTTPS access to
`download.geonames.org`; their settings are on the
[Visitor Map]({% link pages/control-server.md %}). Installation enables cron and
creates the city refresh launcher; the first enabled check downloads missing
city data. Existing datasets and custom or disabled schedules are retained.
The automatic package installation uses apt on Debian/Ubuntu systems. Run
deployment from a checkout separate from `/opt/prod/mycount`.

The installer creates the `mycount` database and database account, a Linux
service account, and `/etc/mycount/database.env` with root-only permissions.
It reuses existing credentials without resetting the database password.
It copies the application to `/opt/prod/mycount`, creates its `.venv`, applies
the visitor schema and installs and starts `mycount-server.service`
and `mycount-control.service`, plus the `mycount-router.service` background worker.
It checks both local health endpoints before
configuring Caddy. Upgrades stop the affected services before updating dependencies
and code; an installation failure can leave them stopped. Correct the reported error and
rerun the installer. Installation is not a transactional rollback mechanism.

See [Uninstall]({% link pages/uninstall.md %}) for removal that preserves data.
For an existing installation, use the [upgrade script]({% link pages/upgrading.md %})
to deploy changes.

Runtime defaults are in `mycount/constants/DMyCount.py`. The collector listens
on `127.0.0.1:36666`. Caddy serves public HTTPS on port `443`, routing `/count`,
`/get_count`, and `/health` to the collector and forwarding visitor addresses. The
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

Review the public hostname in `mycount/constants/DCaddy.py` before installation.
The installer discovers the router with `upnpc` and uses the reported local LAN
IPv4 address of the host running the installer, such as wintermute. Reserve that
address in DHCP. The public hostname must resolve to this router's public address.
The installer repairs missing or incorrect TCP mappings for ports 80 and 443
to this machine and reads the router's rules again to verify changes. Correct
mappings are left in place. Other
ports and UDP mappings are preserved. Port 80 supports automatic public certificate
issuance and renewal; keep it reachable. Existing LAN-only site restrictions
remain in place. The installer also enables `mycount-router.service`, a separate
background worker that checks immediately on startup and every five minutes.
It restores missing or incorrect mappings after router resets and verifies the
result. Router discovery and command failures are logged and retried on the
next check; each `upnpc` command has a 30-second timeout. Inspect the worker with
`journalctl -u mycount-router.service`. It runs as the MyCount service user and
does not need database credentials or root privileges.

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
    @collector path /count /health /get_count
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

## BMGeoIP service

MyCount calls `http://geoip.osoyalce.com:54300/api/lookup` for each public visitor
address. The hostname, port, and five-second timeout are defined in
`mycount/constants/DGeoIp.py`. BMGeoIP must be reachable from the deployed host;
its API is intended for a trusted network and has no authentication. BMGeoIP owns
dataset downloads, imports, and refresh scheduling. MyCount does not create local
range tables or download IP-range datasets. Full setup removes a legacy
`/etc/cron.d/mycount-geoip` schedule; existing reference tables are left untouched.

Both IPv4 and IPv6 are supported. IPv4-mapped IPv6 addresses are normalized to
IPv4; non-global addresses receive an empty location without a service request.
When ranges overlap, MyCount selects the greatest numeric start address and then
the smallest end address, preserving its former local lookup behavior.

New visits store country code and name, region, city, latitude, longitude, postal
code, and timezone as a location snapshot. Empty provider values become NULL,
coordinates become numbers, and postal codes remain text. Historical snapshots
are preserved. Existing missing country names are backfilled from recognized ISO
codes during visitor schema setup; supplied names remain unchanged.

A successful lookup with no matching range records the visit with an empty
location. A timeout, service error, or invalid response returns HTTP 503 from
`/count` and does not save that visit. The browser does not retry failed collection.
The collector's `/health` endpoint checks the HTTP listener, not BMGeoIP availability.
