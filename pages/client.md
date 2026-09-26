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

Use a fixed, non-personal label for `data-site`.

An empty or omitted endpoint disables collection. Configured endpoints must use HTTPS and
must not contain credentials. The endpoint URL is public; do not embed secrets.

## Collection

The client sends JSON using `POST` to the configured URL without cookies.
The [client source]({{ '/client/mycount.js' | relative_url }}) defines the
current payload. The planned fingerprinting support described in the
[project mission]({% link pages/project-mission.md %}) is not yet implemented.

## Service requirements and manual verification

The collector skeleton accepts the client's JSON payload at `/` and returns
`204` after storing an event. See [installation]({% link pages/installation.md %})
for setup. Public HTTPS routing and trusted visitor-IP forwarding remain
deployment work.

Because the site and service have different origins, the service must handle
the browser's CORS preflight (`OPTIONS`) for JSON requests. Allow the origin
`https://mycount.osoyalce.com`, method `POST`, and header `Content-Type`.
Include `Access-Control-Allow-Origin` on the actual response too. Add other
test origins explicitly as needed. CORS is not authentication or protection
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
