---
name: bmforge-security-events
description: Publish trusted, request-scoped security events to a service's systemd journal without IP handling, counting, retries or blocking logic in application business code. Independent of HTTP, ZMQ, Fail2ban and nftables.
---

# Fire-and-forget journal security events

Read `references/specification.md`, `references/engineering-contract.md` and the bundled `assets/SecurityEvents.py` before implementation. This optional producer skill has **no component prerequisites**, including ZMQ and Fail2ban. Installing it only pins the standard and asset; do not touch host logging, service units or other repositories on skill selection.

- Copy/adapt `assets/SecurityEvents.py` into the application's own `interface/` layer. Give business code just `security_events.emit("abuse")`; it passes **no IP**, count, ban duration, service endpoint or other policy. It makes no blocking request, no acknowledgement wait, no retry, no cache and no worker-wide counter.
- At the existing request/transport boundary, resolve the trusted **numeric** IPv4/IPv6 source and bind it with `trusted_source(...)` for the lifetime of that request. For proxies, only accept a value from an explicitly trusted immediate peer whose proxy overwrites the header. Do not use arbitrary forwarded headers or visitor-supplied payload fields. Reset the context after each request and test concurrency.
- Use the application's existing logger with **message-only** formatting to systemd stdout/stderr, captured by journald. Set the unit's `StandardOutput=journal` and `StandardError=journal` as needed; keep ordinary diagnostics independent. No new log file, rotation, watcher, file backend, broker or journal client library.
- Emit one line `yyyy-mm-dd hh:mm:ss SECURITY event=<approved> ip=<trusted numeric address>` with no user-controlled free text, extra prefix or newline. Keep the event vocabulary in application constants. The producer owns formatting and safe address binding, not abuse detection, rate thresholds or enforcement.
- For an enforcement integration, **Fail2ban** consumes journal events, uses its native `findtime`/`maxretry` per address and invokes the existing ZMQ action in the blocking project. One confirmed-abuse event may warrant `maxretry = 1`; avoid layering an application-side counter over a second Fail2ban threshold. The producer must never depend on Fail2ban/ZMQ/nftables.
- Mark the owning implementation with `BMFORGE_COMPONENT = {"id": "bmforge.security-events", "spec_version": "0.1.0"}` and exercise the specification's unit, ingress/trust, journal and application-request integration checks. Test journal delivery with the **actual** producing systemd unit and native Fail2ban journal backend. If those tools cannot run locally, report the remaining acceptance checks; do not invent success or perform an unapproved production deployment.
- Keep this small. The journal stream is a best-effort fire-and-forget channel; do not promise guaranteed delivery or invent a resilience system. BMCyber already owns IP blocking and kernel expiry; no new nftables functionality or revalidation gate is part of this producer skill.
