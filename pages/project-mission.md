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

The browser component will run in a GitHub Pages page on a Jekyll site.
JavaScript is the proposed language. When a visitor loads the page, it will
send a payload containing browser information to the MyCount service.

The service will run on one of the project owner's machines. It will receive
the payload, use available request information such as the visitor's IP
address to derive metadata, and store visitor records in MariaDB. Personal
information used during processing will be discarded rather than stored.

## Useful visitor metadata

Geolocation is a core metric. MyCount will use IP-derived approximate location
to help teams understand where their audience is. The geographic detail to
retain remains an architecture decision.

Other metadata of interest includes:

- Browser language preferences.
- Device category, such as desktop, phone, or tablet.
- Operating system.
- Browser family.

These metrics will help teams understand their audience and inform
localization, design, marketing, sales, and customer service decisions.

## Privacy boundaries

MyCount will retain useful metadata without storing personal information such
as IP addresses. An IP address may be used transiently to derive location,
then must be discarded. This boundary must also apply to application and
proxy logs.

The browser component will use no cookies or other client-side tracking
storage. The purpose is to understand the audience, not to identify individual
visitors. The retained fields and their level of detail must respect that
purpose.
