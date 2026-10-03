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

The Report filters box starts with the last 30 calendar days, including today,
and **Exclude bots** checked. Choose From and Through dates (inclusive), a
report timezone, and the bot filter, then select **Apply filters**. Ranges are
limited to 366 days. With JavaScript, the initial report selects the browser's
IANA timezone automatically; without JavaScript it starts in UTC. Filters and
pagination links retain the selected timezone and range in the URL.

The range and bot filter apply together to site totals, expanded pages,
locations, recent visits, referrers, and charts. Last Visited is the latest
matching visit within that range. Visits by Location stays at the top of the
right column. Uncheck Exclude bots to include bots.
The filter excludes visits flagged as bots and historical Googlebot/GoogleOther
records identified by browser family, including older missing or incorrect bot
flags. Other unknown bot statuses remain included. The choice is retained in
the page URL; opening `/` starts with bots excluded.

Beside it, Visits by Location groups matching page views across sites by
Country, State/Province, and City, with a Visits column. Unknown
or empty fields display `---` and remain included in the counts. Rows start
with the highest visit count, then country name/code, state/province, and city for ties;
Country displays a Unicode flag before the stored full name when its code is
recognized; grouping uses the country code and sorting uses the country name.
Column headers allow sorting. Both tables end with a bold, right-aligned
Total row showing the sum of Visits (zero when empty), which stays at the
bottom when sorting. The tables stack on narrow screens.

Recent Visits appears below Visits by Site in the left column. It shows
50 visits per page matching the date range and bot filter, newest first (newest record first
when timestamps tie), with Date (`YYYY-MM-DD`), Time (`HH:MM AM/PM`), City, and URL. Cities are prefixed with a Unicode country flag when the stored country code
is recognized. Unknown cities display `---`; unknown countries have no flag.
Dates and times use the browser timezone. Visits by Location and Last refresh
keep their positions. Recent visits are read in the same transaction as the
other metrics. **Older visits** loads the next page; **Newest visits** returns
to the first page. Paging uses receipt time and record ID, so new arrivals do
not shift the older-page position. Chart totals cover the entire selected
range regardless of the recent-visit page.

Recent Visits and Visits by Location show the first 10 records in a scrollable
area. Scroll within Recent Visits to see the remaining records on its current
50-record page. Location and referrer tables contain groups within the selected
range. The visible height adjusts to wrapped rows and window size.

Referrers appears below Visits by Location in the right column. It groups visits
by referrer host, ordered by visit count, with missing referrers labeled
Direct / Unknown. The table includes internal referrers, supports column sorting,
and shows a total for all matching visits. It uses the same bot filter and
read-only transaction as the other metrics, loading all hosts into a 10-row
scroll area.

Click a site row to expand or collapse its page table. The site-name button
also works with Enter or Space. Each page shows its full recorded URL, visit
count, and browser-local last-visited time. Pages are sorted by visits descending,
then URL for ties. Multiple sites can remain expanded together. Site, page, and location
metrics are read in one read-only database transaction when the page loads;
expanding a row does not reload the report. Reloading collapses the rows.

The title bar has **Metrics** (`/`), **Reference** (`/reference`), and
**Marketing** (`/marketing`) links without brackets. Each page hides its own
navigation link.
Marketing records promotional posts using a simple form: Posted At defaults to
the current browser-local time as `yyyy-mm-dd hh:mm` and remains editable;
Platform offers Discord, Email, Facebook, LinkedIn, Reddit, and X in alphabetical order;
Posting URL accepts an HTTP(S) link; Notes is optional. Saving stores the posting
time in UTC and generates `created_at` in the database. Installation and upgrade
create the `marketing_posts` table without replacing existing events.

An optional PNG screenshot (up to 10 MiB) can be attached when recording a post.
The server checks the PNG structure and checksums, saves it with a generated
filename under `pages/marketing` in the application directory, and stores its
relative path in `marketing_posts.screenshot_path`. Existing posts have a NULL
reference. A confirmed transaction failure removes the new screenshot. If the
COMMIT reply is lost, the server retains the file because the database may
already reference it. The error page retains a submission ID: retry that same
form to confirm the original posting without creating a duplicate. If no post
was saved, select the file again before retrying. Reloading the form starts a
new submission. A database uniqueness constraint also protects simultaneous
retries. Legacy posts retain NULL submission IDs.

Interrupted saves and simultaneous retries can leave unreferenced files. With
the control service stopped and database credentials supplied in the process
environment, reconcile from the installed application directory:

```sh
.venv/bin/python -B -m mycount.activity.ReconcileMarketingScreenshots
```

Run this as the service account or another account with access to the screenshot
folder. It checks generated PNG filenames older than one day against current
database references, removes only unreferenced files, and prints the removed
count. Recent uploads, referenced files, and other filenames are preserved.
A failed database check stops reconciliation before deleting that file.
Restart the control service afterward.

Use **View Screenshot** in the event table to display the image, then click the
image to open it at full size. Clicking a chart posting marker also opens that
event's screenshot. The control server serves only generated PNG filenames from
this folder. Installation and upgrade create the folder for the service account
and allow systemd write access specifically to it. Upgrades and uninstallation
preserve uploaded screenshots alongside the retained database records.

The Marketing line chart shows daily visit totals across all sites in the
selected report timezone and date range, including zero-visit days, with bots
excluded by default. The promotional-post table and markers use the same range.
Daily visit totals are calculated in the database using UTC intervals for each
local calendar day, including 23- and 25-hour daylight-saving days. MariaDB
timezone tables are not required, and individual visit timestamps are not sent
to the browser for aggregation.
The visits line uses spline interpolation.
Each promotional post adds a vertical line at its posting time. Hover over its
diamond marker to see the platform and timestamp; click it to scroll to the
post's URL and notes in the table below. Markers also appear when no visits have
been recorded. These totals describe traffic changes; they do not attribute
visits to a specific post or project.
Reference displays one [data inventory table]({% link pages/collected-data.md %})
with Source, Source Details, Table, Column, and Details. It includes optional browser details,
all GeoIP source fields, and storage mappings; unretained values show `---` in
both storage columns. The reference content is static; its title bar queries the
earliest recorded visit. If that query fails, Reference remains available with
the Counting since line hidden, and the error is logged.

All three pages display Counting since followed by the earliest recorded visit's
date (for example, September 23, 2026), in the browser's local timezone.
This date includes all sites and bots regardless of the current filter. The
line is hidden when no visits have been recorded or the date is unavailable.
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
data access layer, independently of the collector. `ReadReports` owns report
query selection, read-only snapshot transactions, and connection cleanup;
the HTTP handler validates query inputs and renders the returned report. `GET /health` returns HTTP 200
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
