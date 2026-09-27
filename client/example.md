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

The client uses no cookies. Planned browser fingerprinting is not yet
implemented in this example. See the [project mission]({% link pages/project-mission.md %})
for the reporting goals.

<script defer src="{{ '/client/mycount.js' | relative_url }}"
        data-endpoint="{{ site.mycount.endpoint | escape }}"
        data-site="mycount"></script>
