---
title: Control server
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

Installation and upgrade enable and start `mycount-control.service` alongside
the visitor collector. Open `http://<server>:61777/` to see the MyCount Control
banner, using R3el's masthead layout with a dark orange palette.

The site table shows Visits by Site, Visits, and Last Visited, ordered by visit count
(highest first), then site name. Visits counts recorded page views across all pages for that site, subject to
the active filter. Last Visited is the latest received
visit, displayed in browser-local time as `YYYY-MM-DD HH:MM`.

The Filters box above Visits by Site has **Exclude bots** checked by default.
Visits by Location stays at the top of the right column. Changing it reloads the page and filters site totals, expanded pages, locations,
last-visited timestamps, and total rows together. Uncheck it to include bots.
The filter excludes visits flagged as bots and historical Googlebot/GoogleOther
records identified by browser family, including older missing or incorrect bot
flags. Other unknown bot statuses remain included. The choice is retained in
the page URL; opening `/` starts with bots excluded.

Beside it, Visits by Location groups matching page views across sites by
Country, State/Province, and City, with a Visits column. Unknown
or empty fields display `---` and remain included in the counts. Rows start
with the highest visit count, then country name/code, state/province, and city for ties;
Country displays the stored full name; grouping uses its country code.
Column headers allow sorting. Both tables end with a bold, right-aligned
Total row showing the sum of Visits (zero when empty), which stays at the
bottom when sorting. The tables stack on narrow screens.

Click a site row to expand or collapse its page table. The site-name button
also works with Enter or Space. Each page shows its full recorded URL, visit
count, and browser-local last-visited time. Pages are sorted by visits descending,
then URL for ties. Multiple sites can remain expanded together. Site, page, and location
metrics are read in one read-only database transaction when the page loads;
expanding a row does not reload the report. Reloading collapses the rows.

The title bar has **Metrics** (`/`) and **Reference** (`/reference`) links.
Reference displays one [data inventory table]({% link pages/collected-data.md %})
with Source, Source Details, Table, Column, and Details. It includes optional browser details,
all GeoIP source fields, and storage mappings; unretained values show `---` in
both storage columns. This is static documentation without database queries.
Last refresh appears on its own row below the title bar in
browser-local time as `MMM DD - HH:MM` (for example, `Sep 27 - 14:36`).

Click a Metrics column header to sort by site/page name, numeric visit count,
or last-visited time. Click again to reverse the order. Expanded page tables
stay with their site when sorted, and each page table can be sorted independently.
Column buttons also work with Enter or Space.

Reload the page to refresh the metrics and timestamp. Empty databases show
“No visits match the current filters.” Database failures return HTTP 503 with a short message;
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
