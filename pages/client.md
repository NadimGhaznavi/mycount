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
  endpoint: "https://count.osoyalce.com/"
```

Add this script once to a page with Jekyll front matter, or to its layout:

{% raw %}
```html
<script defer src="{{ '/client/mycount.js' | relative_url }}"
        data-endpoint="{{ site.mycount.endpoint | escape }}"
        data-site="mycount"></script>
```
{% endraw %}

Use a fixed, non-personal label for `data-site`. The client records the visited
page's origin and path, excluding its query string and fragment. For example,
`https://example.com/products/?campaign=spring#pricing` is sent as
`https://example.com/products/`. It does not collect the referring page.
Use the client on pages whose paths do not contain personal information.

An empty or omitted endpoint disables collection. Configured endpoints must use HTTPS and
must not contain credentials. The endpoint URL is public; do not embed secrets.

## Request contract

The client sends JSON using `POST` to the exact configured URL. For example:

```json
{
  "schema_version": 1,
  "event": "page_view",
  "site": "mycount",
  "url": "https://mycount.osoyalce.com/client/example.html",
  "languages": ["en-CA", "en"],
  "user_agent": "<browser-provided user-agent string>"
}
```

Language preferences are in browser-provided order. The service should derive
browser family, operating system, and device category from the user agent and
discard the raw string. These are browser-reported hints and may be reduced or
spoofed; they are not verified facts about the visitor.

The client does not look up an IP address or ask for device location. The
service must derive approximate geography from the incoming connection's IP
and discard that address. Only approved metadata belongs in MariaDB; raw
payloads, IP addresses, and raw user agents must not be retained in service or
proxy logs.

Requests use `credentials: "omit"` and `referrerPolicy: "no-referrer"`. There
are no cookies, browser storage, fingerprints, or persistent visitor IDs.
These are page-view events, not unique-visitor counts.

## Service requirements and manual verification

The service implementation is still pending. The configured root URL is the
initial collection target; update it if the service defines a different path.
It must accept the JSON contract above, validate incoming data, and return a
successful HTTP status such as `204` after accepting an event.

Because the site and service have different origins, the service must handle
the browser's CORS preflight (`OPTIONS`) for JSON requests. Allow the origin
`https://mycount.osoyalce.com`, method `POST`, and header `Content-Type`.
Include `Access-Control-Allow-Origin` on the actual response too. Add other
test origins explicitly as needed. CORS is not authentication or protection
against forged visitor events.

Open the live example with browser developer tools, then inspect the Network
panel. Confirm the preflight succeeds and one JSON `POST` is sent with the
expected fields and without a Cookie or Referer header. Add a query string and
fragment to the example's URL and confirm neither appears in the payload.
Reload to send another
event. Clear the endpoint and rebuild the site to verify collection stops.

HTTP and network failures produce a short console warning without logging the
payload. The client does not retry, since a failed response does not prove the
service failed to receive the event. Delivery is best effort; blockers and
network failures can prevent collection.

See the browser API references for [Fetch credentials](https://developer.mozilla.org/en-US/docs/Web/API/Request/credentials)
and [keepalive](https://developer.mozilla.org/en-US/docs/Web/API/Request/keepalive).
