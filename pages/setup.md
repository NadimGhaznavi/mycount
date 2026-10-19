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

## Network configuration

`DMyCount.CMDB_NETWORK` in `mycount/constants/DMyCount.py` is the shared
network inventory for MyCount and CMDB discovery. Each entry contains
`(use, interface, port)`. Keep the four uses: `http` and `https` for Caddy,
`report` for MyCount Control, and `backend` for the collector.

Server bindings, Caddy's listeners and upstream, public router mappings, and
deployment health checks use this inventory. Apply changes through the normal
deployment workflow. Control's `--host` and `--port` arguments still override
its defaults for an individual invocation. Database and GeoIP connections have
separate settings because they are outbound dependencies.

---

## Uninstall MyCount

Navigate to the local git repo you created when you downloaded and installed **MyCount**:

```sh
cd mycount
sudo ./scripts/uninstall.sh
```

If you deleted the local repo, you can just `git clone` it again.