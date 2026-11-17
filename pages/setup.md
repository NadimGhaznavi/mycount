---
title: Download, 
layout: single
author_profile: true
---

## Download and Install MyCount

```sh
sudo git clone https://github.com/NadimGhaznavi/mycount
cd mycount
sudo ./scripts/install.sh
```

## Start and stop services

From the checkout or installed directory, run:

```sh
sudo ./scripts/services.sh start
sudo ./scripts/services.sh stop
```

Start runs the collector and Control sequentially, followed by the router
worker when enabled. Stop includes the router worker and uses the reverse
order. The command stops at the first failed service operation.
Use `./scripts/services.sh --help` to display usage.

Automatic UPnP forwarding is disabled by default through
`DRouterMappings.ENABLED = False` in `mycount/constants/DRouterMappings.py`.
Configure the router's HTTP/HTTPS forwarding manually when this setting is off.
Installation and upgrade stop and disable `mycount-router.service` when off,
and enable and start it when on. Caddy setup and `scripts/restart.sh` also
honor the setting. To restore automatic forwarding, set the constant to `True`
in the checkout before deploying an update.

The separate `mycount-isoforest.service` job runs only when the minute cron
check starts it. Its recurring schedule and queued runs are managed from the
web interface's **IsoForest** page. See
[IsoForest traffic filtering]({% link pages/isoforest.md %}) for operation and
stored evidence.

## Network configuration

Installation creates `/opt/prod/mycount/conf/mycount.json` using the defaults
in `DMyCount.CMDB_NETWORK`. Existing files are preserved during reinstall and
upgrade. CMDB discovery continues to read the default inventory from the code.

The generated file contains all four network uses: `http` and `https` for
Caddy, `report` for MyCount Control, and `backend` for the collector. Each use
has an IPv4 `interface` and an integer `port` between 1 and 65535. For example,
to change only the report server's binding, the file can contain:

```json
{
  "network": {
    "report": {
      "interface": "127.0.0.1",
      "port": 62000
    }
  }
}
```

Omitted uses and fields take their values from `CMDB_NETWORK`. When no config
file exists, the defaults apply. Invalid files cause startup to fail with a
field-specific error rather than silently ignoring the settings.

Edit the production file, then apply the settings from the installed directory:

```sh
sudoedit /opt/prod/mycount/conf/mycount.json
cd /opt/prod/mycount
sudo ./scripts/restart.sh
```

The restart command validates the config, regenerates and reloads Caddy,
and restarts the collector and report server. When UPnP is enabled, it also
updates the public router mappings and restarts the router worker; otherwise
it stops and disables that worker. Each MyCount process reads its configuration
once; edits take effect after restart. Use this command when changing network
settings so Caddy's upstream and listeners are also updated.

Control's `--host` and `--port` arguments still override its configured binding
for an individual invocation. Database and GeoIP connections retain their
separate settings because they are outbound dependencies.

---

## Uninstall MyCount

Navigate to the local git repo you created when you downloaded and installed **MyCount**:

```sh
cd mycount
sudo ./scripts/uninstall.sh
```

If you deleted the local repo, you can just `git clone` it again.
