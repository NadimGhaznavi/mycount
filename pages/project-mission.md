---
title: Project Mission
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

MyCount has two purposes: to test the mydynip system through a real application
and to provide useful visitor metrics for marketing, sales, customer service,
and other teams.

The [browser client and live example]({% link pages/client.md %}), HTTPS
collector, visitor storage, and installation scripts are implemented.

## Two components

The JavaScript browser component runs in a GitHub Pages page on a Jekyll site
and sends an event to the MyCount service when a visitor loads the page.

The service runs on one of the project owner's machines, processes incoming
events, and stores reporting data in MariaDB.

## Audience reporting

MyCount will help teams understand traffic, geographic reach, and audience
preferences to inform marketing, sales, localization, design, and customer
service decisions.

The client uses a persistent random browser ID in first-party local storage to
associate page views and estimate unique browsers per site. These are estimates,
not exact counts of people, and cannot deduplicate people across websites.
Browser fingerprinting is not implemented. Views without an ID remain
unidentified in reports.

## Privacy boundaries

MyCount uses no cookies. First-party local storage holds a random per-site
browser ID, which is retained with page views as a pseudonymous identifier;
collection is not anonymous. Visitor IP addresses are not retained, including
in application and proxy logs. Collection continues without an identifier
when browser settings prevent storage.
