---
title: Client Example
layout: single
author_profile: true
---

[Documentation index]({% link index.md %}) · [Client guide]({% link pages/client.md %})

This page runs the MyCount client. Each page load attempts to send one visitor
event to the configured collection service. Reloading creates another event.

The client uses no cookies. Planned browser fingerprinting is not yet
implemented in this example. See the [project mission]({% link pages/project-mission.md %})
for the reporting goals.

<script defer src="{{ '/client/mycount.js' | relative_url }}"
        data-endpoint="{{ site.mycount.endpoint | escape }}"
        data-site="mycount"></script>
