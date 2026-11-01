---
title: Security Events and BMCyber Integration
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

The collector publishes security events through `mycount-server.service`'s
systemd journal. Fail2ban can count these events per IP across all collector
workers and invoke BMCyber's existing ban action. MyCount publishes events
without waiting for acknowledgement, keeping counters, or calling BMCyber.

## Published events

| Event | When it is emitted | Agreed companion threshold |
| --- | --- | --- |
| `collection_request` | Once for each `POST /count` with a verified client address, before origin checking, JSON parsing, geolocation, or persistence. | 60 events from one IP within 60 seconds. |
| `malformed_payload` | Additionally when an allowed-origin POST has malformed JSON, an unsupported content type, an oversized body, or fails visit-payload validation. | 5 events from one IP within 60 seconds. |

A malformed submission contributes to both counts. Counts combine all sites
and page URLs for an IP. Health requests, OPTIONS preflights, counter reads,
other routes and unsupported methods do not publish either event. An origin
rejection publishes only `collection_request`: its body is not inspected.
Database/geolocation outages are operational errors, not malformed payloads.
Existing bot classifications do not produce a ban event.

Each journal `MESSAGE` contains exactly one line, for example:

```text
2026-11-01 10:00:00 SECURITY event=collection_request ip=192.0.2.10
2026-11-01 10:00:00 SECURITY event=malformed_payload ip=192.0.2.10
```

The timestamp is local time at second precision. Event names are fixed
application constants. Records contain no URL, payload, user-agent text, or
other free text supplied by a visitor. The security logger writes the message
without additional prefixes to stderr; the service explicitly sends stdout
and stderr to journald. Normal diagnostics keep their existing configuration.

## Trusted source attribution

Caddy overwrites `X-MyCount-Client-IP` with its observed client address.
MyCount accepts this header only when the immediate peer matches its
configured local backend/proxy address. Otherwise it uses the directly
observed peer, ignoring forwarded headers. The existing deployment binds the
backend to loopback; maintain that proxy/listener boundary.

Sources must be numeric IPv4/IPv6 addresses. Missing, malformed, scoped,
unspecified, multicast, or multiple addresses are rejected. A trusted proxy
request missing the client header returns 400 rather than substituting the
proxy's address. Requests without trustworthy attribution produce neither
event. Validated addresses are bound only for the current request and are
restored even when the handler raises.

## Companion configuration and activation

MyCount does not install or configure Fail2ban or BMCyber. Required companion
changes are recorded in the [unreleased changelog]({% link CHANGELOG.md %}).
They include separate, initially disabled flood and malformed-payload jails,
native `backend = systemd`, and a journal match restricted to
`_SYSTEMD_UNIT=mycount-server.service`. The consumer must match these event
names rather than the older `fail2safe` event. BMCyber's current file-based
jail cannot consume this producer without those changes.

The host Fail2ban interpreter needs native systemd journal bindings (such as
the distribution's `python3-systemd` package); MyCount needs no new Python
package. Fail2ban owns the two count/window thresholds. Its ticket interval
and BMCyber's existing 20–24-hour kernel block duration remain separate.
A resulting ban affects inbound traffic to the entire host.

Before activation, verify real requests through Caddy and the installed
collector service. Inspect the journal using:

```sh
journalctl -u mycount-server.service -o cat
journalctl -u mycount-server.service -o verbose
```

Confirm one `collection_request` per POST, an additional `malformed_payload`
only for the cases above, original IPv4/IPv6 addresses, and the actual trusted
`_SYSTEMD_UNIT` metadata. On a disposable systemd host with the companion
configuration, use native Fail2ban journal matching to verify timestamps,
both thresholds and their windows, exclusions, multiple workers, and receipt
of the correct BMCyber ban request. Logger/WSGI tests alone do not prove that
native journal integration works.

Journal publication is best effort: rate limiting or output failures may lose
events. This is asynchronous abuse detection, not a synchronous HTTP rate
limiter or DoS protection. MyCount does not return 429 merely because an IP
has reached a companion threshold, and it makes no delivery or ban guarantee.
