---
title: Control server
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

Installation and upgrade enable and start `mycount-control.service` alongside
the visitor collector. Open `http://<server>:61777/` to see the MyCount Control
banner, using R3el's masthead layout with a dark orange palette.

The control server currently displays only the banner. It runs independently
of the collector and does not connect to the database. `GET /health` returns
HTTP 200 with JSON identifying `mycount-control`.

Defaults are in `mycount/constants/DControl.py`. The server listens on
`0.0.0.0:61777`; installation does not add a Caddy route or router forwarding
for this port.

View service status and logs with:

```sh
systemctl status mycount-control.service
journalctl -u mycount-control.service -f
```

For standalone startup from a checkout with dependencies installed:

```sh
.venv/bin/python -B -m mycount.server.ControlServer --host 127.0.0.1 --port 61777
```

Uninstall stops and removes both MyCount services.
