---
title: Security Event Producer
lang: en
locale: en-US
language_name: English
component_id: "bmforge.security-events"
spec_version: "0.1.0"
spec_status: "draft"
translation_key: bmforge-security-events
---

**Component ID:** `{{ page.component_id }}` · **Specification:** `{{ page.spec_version }}` ({{ page.spec_status }})

## Intent and boundaries

Give an application one small **fire-and-forget security-event interface**. Application business logic emits a named event such as `security_events.emit("abuse")`. It does not supply an IP, count requests, manage retries, await an acknowledgement, request bans, cache state or know that Fail2ban/BMCyber exists. The application's existing **trusted ingress adapter** binds a validated source address outside business logic. The producer then writes one canonical record through the service's systemd journal stream.

This is an **independently selectable** skill: it requires **none** of `bmforge-http`, `bmforge-zmq`, `bmforge-fail2ban` or `bmforge-nftables`. An application may use a different HTTP stack or have no HTTP transport. Do not install, configure or control Fail2ban, nftables, another event daemon, a broker, a queue, an IP-ban map, a database, or a general logging framework. It is not a telemetry or audit-storage system.

## Approved implementation technology

The canonical producer is `assets/SecurityEvents.py`, copied into the application's own `interface/` package and adapted only for its constants and existing logger. BMForge is never a production import.

| Origin | Module/tool | Purpose |
| --- | --- | --- |
| Python stdlib | `contextlib`, `contextvars` | Bind and restore one verified source for each request, isolated between threads/async tasks and Gunicorn workers |
| Python stdlib | `datetime` | Write local-time timestamps with second precision |
| Python stdlib | `ipaddress` | Validate and normalize numeric IPv4/IPv6 sources once at the ingress boundary |
| Python stdlib | `logging` | Emit one ordinary application-owned log record |
| Python stdlib | `re` | Validate fixed event identifiers |
| Host | `systemd-journald` and a systemd service unit | Capture stdout/stderr; no Python systemd binding, journal client library or separate output file |

`bmforge-security-events` introduces no third-party Python dependency. The systemd journal is the **only supported production delivery channel** for this component. Existing application diagnostics may continue using their normal logging configuration.

## Producer and trusted source

Only a transport/ingress adapter, before invoking application logic, may resolve the source. For direct connections, select the actual peer address. Behind a reverse proxy, use a forwarded value **only if** the connection came from an explicitly trusted proxy and that proxy replaces the header using its own observed client connection. A random incoming `X-Forwarded-For`, custom header, analytics payload field or claimed IP is untrusted. Normalize numeric IPv4/IPv6; reject missing, malformed, untrusted or ambiguous sources rather than attributing them to the proxy or a fabricated address.

Bind the verified value to the request context, not to a mutable process-wide variable, and restore the context in `finally` after handling. In a multithreaded/async server this prevents cross-request attribution; different Gunicorn workers naturally have separate contexts. If no trusted source has been bound, the producer fails visibly rather than emitting a potentially dangerous misattributed security event. The business handler neither receives nor manipulates an IP for security-event production.

Illustrative integration in the application's existing HTTP adapter (the adapter supplies its **already-trusted** address resolver):

```python
with security_events.trusted_source(trusted_client_address(request)):
    return application_handler(request)

# Deep in application logic, after it decides this action is significant:
security_events.emit("abuse")
```

The producer emits the event immediately and returns `None`. It never waits for Fail2ban, asks for a ban, tracks retries, implements rate thresholds or persists a queue. A logging failure cannot be interpreted as a confirmed ban. The application owns *which* semantic events to issue; separate Fail2ban jail configuration owns any count/window needed to turn emitted events into an enforcement request.

## Canonical journal delivery

**One source: journald.** A production systemd service must send its security logger to the journal via stdout/stderr. Prefer a dedicated `logging.StreamHandler(sys.stderr)` with `logging.Formatter("%(message)s")` and no duplicate propagation or Gunicorn prefix. Reuse the application's existing logging infrastructure; do **not** create a logfile, watcher, file-rotation policy or new daemon. The producer's logger must deliver exactly the formatted record, without an extra timestamp, log level, prefix, suffix, embedded newline or application exception data.

A canonical UTF-8 `MESSAGE` is:

```text
2026-10-31 17:19:00 SECURITY event=abuse ip=192.0.2.10
2026-10-31 17:19:01 SECURITY event=abuse ip=2001:db8::10
```

Use local `yyyy-mm-dd hh:mm:ss`, a fixed literal `SECURITY`, one allowlisted ASCII event identifier and one canonical numeric address. Keep user-controlled URLs, headers, usernames, payloads, raw log messages and newline characters out of the matched record. The journal independently supplies trusted unit/timestamp metadata. This embedded local-time stamp retains compatibility with native Fail2ban date extraction and the existing security-event format.

Configure/verify the service unit's `StandardOutput=journal` and `StandardError=journal` (the systemd defaults unless overridden), and inspect the installed unit and journal. An application logger must actually write to one of those streams; a logger that only writes to files does not qualify. Journal rate limiting, output failure or service outage can lose events; fire-and-forget is **best effort**, not a delivery or banning guarantee. Do not add application retries, buffering, a queue or fallback transport to hide that limitation.

## Consumer boundary

Native [Fail2ban]({{ site.baseurl }}{% link pages/component-fail2ban.md %}) may read the service's journal entries and count native matches across all workers. The producer never configures a jail. Events meaning *confirmed abuse* normally use one match per request (`maxretry = 1`); an application may instead emit a countable event for Fail2ban to aggregate within its own `findtime`. This is an application-specific policy decision, not two nested counters. Non-security analytics classifications and ordinary invalid requests must not automatically emit a banning event.

The local enforcement service and kernel-owned nftables bans remain separate. A consuming integration should verify that the trusted source is the intended external address and that its journal entry reaches the native Fail2ban action. **Do not retest nftables IP blocking as a prerequisite for this skill:** the blocking service owns that existing contract.

## Native documentation

- [systemd-journald](https://www.freedesktop.org/software/systemd/man/latest/systemd-journald.html) documents service stdout/stderr capture as journal records, separated at newline boundaries.
- [systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html) documents service `StandardOutput`/`StandardError` and journal identifiers.
- [Fail2ban jail.conf](https://github.com/fail2ban/fail2ban/blob/master/man/jail.conf.5) documents the native `systemd` backend and `journalmatch` used by the consumer.

## Installation and acceptance

1. Install or attach the producer skill alone with no ZMQ, Fail2ban, HTTP or nftables dependency; verify the pinned specification and `SecurityEvents.py` asset. Installing a skill performs no host mutation, log configuration or service deployment.
2. Unit-test `emit("abuse")` with a message-only logger, including a valid IPv4 and IPv6 source, no trusted source, unknown/newline event names, forged headers or nonsensical addresses. Test nested, concurrent and restored request context. Assert **no IP parameter on `emit`**, no state tracking or calls to a blocking service.
3. Test the actual application's ingress adapter: a directly observed peer or explicitly trusted proxy supplies the address; a forged forwarded header from an untrusted peer cannot become the event's IP.
4. On a disposable systemd host, trigger an event **through the running application's normal request path**. Confirm `journalctl -u <service> -o cat` shows exactly one canonical `MESSAGE` (and check `journalctl -u <service> -o verbose` for `_SYSTEMD_UNIT`). Verify output is still correct across multiple Gunicorn workers where used.
5. Use Fail2ban's native journal backend and `fail2ban-regex -m '_SYSTEMD_UNIT=<service>' systemd-journal <filter>` to verify real journal matching as well as timestamp recognition, without introducing log files. A fixture-only or mocked logger test does **not** replace this native check. Journal/Fail2ban connectivity must be validated on a host with those services; if not available, report it unverified rather than claiming success.
6. An end-to-end consuming application test starts with a real request, not a synthetic logfile entry, and observes the trusted source, emitted `MESSAGE`, native Fail2ban action and received blocking-service request. Use the existing blocking service's own enforcement tests rather than revalidating nftables itself.

---

[Fail2ban consumer]({{ site.baseurl }}{% link pages/component-fail2ban.md %}) · [HTTP source validation]({{ site.baseurl }}{% link pages/component-http.md %}) · [Component Blueprints]({{ site.baseurl }}{% link pages/component-blueprints.md %})
