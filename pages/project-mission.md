---
title: Project Mission
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

MyCount has two purposes: to test the mydynip system through a real application
and to provide useful visitor metrics for marketing, sales, customer service,
and other teams.

This page describes the intended project. An initial
[browser client and live example]({% link pages/client.md %}) are available;
the visitor collection service is not yet implemented.

## Two components

The JavaScript browser component runs in a GitHub Pages page on a Jekyll site
and sends an event to the MyCount service when a visitor loads the page.

The service will run on one of the project owner's machines, process incoming
events, and store reporting data in MariaDB.

## Audience reporting

MyCount will help teams understand traffic, geographic reach, and audience
preferences to inform marketing, sales, localization, design, and customer
service decisions.

The planned design uses browser fingerprinting to associate page views and
estimate unique browsers. These are estimates, not exact counts of people.
Fingerprinting is not yet implemented in the example client.

## Privacy boundaries

MyCount will use no cookies or client-side tracking storage. Fingerprinting
introduces a retained pseudonymous identifier; the design does not promise
anonymous collection. IP addresses will not be retained, including in
application and proxy logs.
