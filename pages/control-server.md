---
title: Control server
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

Installation and upgrade enable and start `mycount-control.service` alongside
the visitor collector. Open `http://<server>:61777/` to see the MyCount Control
banner, using R3el's masthead layout with a dark orange palette.

The site table shows Sites, Visits, and Last Visited, ordered by visit count
(highest first), then site name. Visits counts all recorded page views, including
known bots, across all pages for that site. Last Visited is the latest received
visit, displayed in browser-local time as `YYYY-MM-DD HH:MM`.

Click a site row to expand or collapse its page table. The site-name button
also works with Enter or Space. Each page shows its full recorded URL, visit
count, and browser-local last-visited time. Pages are sorted by visits descending,
then URL for ties. Multiple sites can remain expanded together. Site and page
metrics are read in one read-only database transaction when the page loads;
expanding a row does not reload the report. Reloading collapses the rows.

The right side of the title bar shows `Last refresh: HH:MM` in browser-local
time. Reload the page to refresh the table and timestamp. Empty databases show
“No visits recorded yet.” Database failures return HTTP 503 with a short message;
details are logged to the service journal.

The control service loads `/etc/mycount/database.env` and reads through the shared
data access layer, independently of the collector. `GET /health` returns HTTP 200
with JSON identifying `mycount-control`, without querying the database.

Defaults are in `mycount/constants/DControl.py`. The server listens on
`0.0.0.0:61777`; installation does not add a Caddy route or router forwarding
for this port.

View service status and logs with:

```sh
systemctl status mycount-control.service
journalctl -u mycount-control.service -f
```

For standalone startup from a checkout with dependencies installed and
`DB_HOST`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` in the environment:

```sh
.venv/bin/python -B -m mycount.server.ControlServer --host 127.0.0.1 --port 61777
```

Uninstall stops and removes both MyCount services.
