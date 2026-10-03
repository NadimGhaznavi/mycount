---
title: Client Example
layout: single
author_profile: true
---

[Documentation index]({% link index.md %}) · [Client guide]({% link pages/client.md %})

This page runs the MyCount client. Each page load attempts to send one visitor
event to the configured collection service. Reloading creates another event.

The collection endpoint for this build is
`{{ site.mycount.endpoint | escape }}`. It should be
`https://count.osoyalce.com/count`.

To verify collection, open your browser's developer tools, select **Network**,
and reload this page. Look for a `POST` to `/count` returning **204**. A successful
POST stores one page view; the preflight `OPTIONS` request does not count as a visit.
If the displayed endpoint is outdated, rebuild and publish the site with the
current `_config.yml`.

The script URL includes this site's build timestamp so a new publication loads
the current client instead of reusing an older cached copy. In the POST payload,
check that `visitor_id` remains the same after reloading and that `search`,
`referrer`, and `client_details` are present.

Recorded visits for this site: <span data-mycount-counter>…</span>.
The counter excludes known bots and reads the total after collection finishes.

The client uses no cookies. A random ID in first-party local storage lets repeat
page views count as one browser for this site. If storage is blocked, views
remain unidentified. See the [project mission]({% link pages/project-mission.md %})
for the reporting goals and limits.

<script defer src="{{ '/client/mycount.js' | relative_url }}?v={{ site.time | date: '%s' }}"
        data-endpoint="{{ site.mycount.endpoint | escape }}"
        data-site="mycount"></script>
