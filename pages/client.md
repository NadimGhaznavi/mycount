---
title: Browser Client
layout: single
author_profile: true
---

[Documentation index]({% link index.md %})

The example client in `client/mycount.js` sends one page-view event when its
deferred script runs. The [live example]({% link client/example.md %}) lets us
develop against our own GitHub Pages site. Collection is enabled on that page
only; other documentation pages do not load the script.

## Add the client to a Jekyll page

Copy `client/mycount.js` into your site's `client/` folder. Set the service URL
in `_config.yml`:

```yaml
mycount:
  endpoint: "https://count.osoyalce.com/count"
```

Add this script once to a page with Jekyll front matter, or to its layout:

{% raw %}
```html
<script defer src="{{ '/client/mycount.js' | relative_url }}"
        data-endpoint="{{ site.mycount.endpoint | escape }}"
        data-site="mycount"></script>
```
{% endraw %}

Use a fixed, non-personal label for `data-site`, such as `mycount` or `ax3l`.
Labels may contain ASCII letters, digits, underscores, and hyphens, must start
with a letter or digit, and must be at most 100 characters long.

The endpoint uses standard HTTPS port 443 and the path `DMyCount.COLLECTION_PATH`.
Keep this static Jekyll setting in sync when changing the hostname or path;
GitHub Pages does not read Python constants.

An empty or omitted endpoint disables collection. Configured endpoints must use HTTPS and
must not contain credentials. The endpoint URL is public; do not embed secrets.

## Collection

The client sends JSON using `POST` to the configured URL without cookies.
The [client source]({{ '/client/mycount.js' | relative_url }}) defines the
current payload. A random browser ID saved in first-party local storage
supports per-site unique-browser estimates.

Each visit can store the following information:

| Information | Source |
| --- | --- |
| Site, page origin/path, separate query string, receipt time in UTC | Client and collector |
| Persistent per-site browser ID | Random UUIDv4 saved in first-party local storage |
| Full referrer and normalized referring hostname | `document.referrer`, as exposed by the browser |
| Continent, country, region, city, approximate latitude/longitude, ZIP/postal code, GeoIP timezone | Server-side IP geolocation |
| Preferred languages, user-agent string | Browser |
| Browser/OS family and version, device category/brand/model, bot classification | User-agent parsing |
| Screen and available dimensions, viewport size, pixel ratio, color/pixel depth | Browser |
| Timezone and UTC offset, platform/vendor, reported CPU threads and approximate memory, touch points | Browser, when available |
| Cookie support, online status, PDF support, automation indicator | Browser, when available |
| Color scheme, reduced-motion preference, Do Not Track and Global Privacy Control signals | Browser, when available |
| Effective connection type, estimated downlink/round-trip time, data-saving preference, navigation type | Browser, when available |

City is approximate: VPNs, proxies, mobile networks, and reference-data gaps
can produce a different city or no city. No precise-location permission is
requested. Browser-reported values can be reduced, unavailable, or spoofed;
bot classification is a hint, not proof that a visit is human or automated.
Missing optional values remain unknown rather than being reported as false or zero.

Referrers identify the immediately preceding site, including same-site navigation.
Direct visits and suppressed referrers are indistinguishable and stored as null.
The full HTTP(S) referrer exposed by the browser is retained, including any
path, query, or fragment it supplies. Referrers containing URL credentials are rejected.
Browser [referrer policies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy)
control what `document.referrer` exposes; collection does not bypass them.
The page URL used for metrics still excludes queries and fragments. The query
string is stored separately in `page_views.search`, preserving its leading `?`
and encoding. Empty means no query; NULL means the client did not supply it.
The current page fragment is excluded. Collection uses
no cookies and does not read page contents or form input. The collector stores
the request's full IPv4 or IPv6 address in `page_views.ip_address` alongside its
GeoIP result. Historical visits retain `NULL`; existing IPs cannot be reconstructed.
Reported privacy preference signals are
stored as metadata; they do not currently change collection behavior.

Deploy the collector and apply its schema upgrade **before** copying the updated
`client/mycount.js` to each website (for Ax3l/R3el, the deployed copy is at
`assets/js/mycount.js`). Older cached clients remain accepted; they omit `search` and send only the
referring origin, so full referrer details require the updated client. Historical rows cannot have missing details reconstructed.
An older collector rejects the new optional fields, so upgrade order matters.

### Unique visitors

The client saves a random UUIDv4 under `mycount.visitor_id.<site>` in the page's
first-party `localStorage`. It reuses the ID on reloads and later visits.
Storage is scoped to the page origin, and the key separates site labels on the
same origin. The collector validates IDs and stores them as `visitor_id` in
`page_views`.

If storage is blocked, full, or the browser cannot create a secure UUID, the
page view is still sent without an ID. Old clients and historical records
also have no ID. Report these views as unidentified, not as zero visitors or
one new visitor per hit. Existing hits cannot be deduplicated retroactively.

These counts represent browsers, not people: clearing site data or changing
browser/device creates another ID; shared browsers share an ID. Private browsing
can discard the ID when the private session ends. IDs are not shared across
sites, so summing site totals does not give globally unique people. Automated
browsers can also receive IDs; known bot views are reported separately.

For all-time totals, `VisitDb.totals_by_site()` provides the same report as:

```sql
SELECT p.site, COUNT(*) AS page_views,
       COUNT(DISTINCT v.visitor_id) AS unique_browsers,
       COUNT(CASE WHEN v.visitor_id IS NULL THEN 1 END) AS unidentified_views,
       COUNT(CASE WHEN v.is_bot = 1 THEN 1 END) AS known_bot_views
FROM page_views v JOIN pages p ON p.page_id = v.page_id
GROUP BY p.site
ORDER BY page_views DESC, p.site;
```

To verify after deployment, load two pages on the same site and reload one.
Page views should increase by three and unique browsers by at most one.
Check the POST payload's `visitor_id` remains the same each time.

### View referrers and cities

The new fields live in `page_views`; less commonly queried browser details are
in its validated `client_details` JSON column. For recent R3el visits:

```sql
SELECT v.received_at, p.url, v.referrer_host,
       v.country_code, v.region_name, v.city_name,
       v.browser_family, v.browser_version, v.is_bot,
       JSON_UNQUOTE(JSON_EXTRACT(v.client_details, '$.timezone')) AS timezone
FROM page_views v
JOIN pages p ON p.page_id = v.page_id
WHERE p.site = 'r3el'
ORDER BY v.received_at DESC
LIMIT 20;
```

## Service requirements and manual verification

From the MyCount checkout, run `python3 scripts/test_ax3l.py` to check public
HTTPS health, Ax3l's CORS preflight, and submission of one synthetic Ax3l visit.
It requires Python 3 and curl, exits nonzero on failure, and prints the unique
`/__mycount_test__/` page URL and SQL to verify the saved visit. It does not retry
POST requests or execute the website's JavaScript.

On the collector host, `python3 scripts/test_ax3l.py --local` tests local Caddy
with certificate validation while bypassing public DNS and router forwarding.
Use the default mode from outside the LAN to verify public reachability.

The collector skeleton accepts the client's JSON payload at `/count` and returns
`204` after storing an event. See [installation]({% link pages/installation.md %})
for setup. Caddy provides HTTPS on public port `443` and forwards visitor
addresses through the local proxy connection.

Because the site and service have different origins, the service must handle
the browser's CORS preflight (`OPTIONS`) for JSON requests. Allow the origin
`https://mycount.osoyalce.com`, method `POST`, and header `Content-Type`.
The allowlist is `DMyCount.ORIGINS` in `mycount/constants/DMyCount.py` and includes
`https://mycount.osoyalce.com` and `https://ax3l.osoyalce.com`. Add exact origins
without paths or trailing slashes, then redeploy the collector. Each allowed
request receives its own origin in `Access-Control-Allow-Origin`; the submitted
page URL must match that request origin. The client supplies the site label.
CORS is not authentication or protection
against forged visitor events.

Open the live example with browser developer tools, then inspect the Network
panel. Confirm the preflight succeeds and one JSON `POST` receives a successful
response. Reload to send another event. Clear the endpoint and rebuild the
site to verify collection stops.

HTTP and network failures produce a short console warning without logging the
payload. The client does not retry, since a failed response does not prove the
service failed to receive the event. Delivery is best effort; blockers and
network failures can prevent collection.

See the browser API references for [Fetch credentials](https://developer.mozilla.org/en-US/docs/Web/API/Request/credentials)
and [keepalive](https://developer.mozilla.org/en-US/docs/Web/API/Request/keepalive).
