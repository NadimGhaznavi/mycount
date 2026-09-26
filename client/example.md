---
title: Client Example
layout: single
author_profile: true
---

[Documentation index]({% link index.md %}) · [Client guide]({% link pages/client.md %})

This page runs the MyCount client. Each page load attempts to send one visitor
event to the configured collection service. Reloading creates another event.

The event contains the site label `mycount`, this page's URL without its query
string or fragment, browser language preferences, and the browser's user-agent
string. The service is intended to
derive geographic, browser, operating system, and device metadata, then discard
personal information and raw input rather than store it.

The client uses no cookies, persistent identifiers, or browser storage.

<script defer src="{{ '/client/mycount.js' | relative_url }}"
        data-endpoint="{{ site.mycount.endpoint | escape }}"
        data-site="mycount"></script>
