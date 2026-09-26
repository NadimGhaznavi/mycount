---
title: Changelog
author_profile: true
layout: single
permalink: /CHANGELOG/
---

# Changelog

## [Unreleased]

## [0.1.0] - 2026-09-26 @ 16:20

### Summary

Establish the MyCount documentation website and development foundation, with
shared coding conventions and a tested release workflow. Add the shared
MariaDB layer and explicit schema setup as the foundation for collection and
reporting. Add local IPv4/IPv6 geolocation and an installer with weekly
reference-data updates.

### Added

- Separate GeoIP download, import, schema, and lookup components using the free ipapi.is IPv4 and IPv6 datasets and the shared MariaDB layer.
- Root installer for the application, database, credentials, systemd service, and weekly GeoIP cron job; refreshes publish both address families together.
- Collector skeleton with HTTP handling, visit preparation, and persistence in separate components.
- `Visit` entity for passing validated visit data between processing activities, independent of database persistence.
- Generic `DbMgr` with parameterized queries, UTC connections, transaction rollback, read-only transactions, and explicit connection cleanup.
- Separate visitor schema activity with reporting indexes and relational constraints, designed for repeatable installation and upgrade setup.
- PyMySQL dependency, focused database tests, and a data access guide linked from the documentation index.
- JavaScript page-view client and Jekyll example targeting `https://count.osoyalce.com/`, with a linked integration guide.
- Project mission documenting the mydynip testing purpose, planned visitor metrics, browser and service components, and privacy boundaries, linked from the homepage.
- Jekyll configuration for `mycount.osoyalce.com` using the dark Minimal Mistakes theme.
- Minimal homepage linking coding guidelines, release management, and the changelog.
- `AGENTS.md` and MyCount coding guidelines covering component responsibilities, constants naming, and focused documentation.
- Python package foundation with `DMyCount.VERSION`, initially `0.0.1`.
- Release script that updates the version and changelog, merges feature work through `dev` to `main`, and publishes an annotated tag.
- Six isolated release tests covering successful publication, prereleases, invalid input, dirty working trees, duplicate versions, and help output.
- Release guide documenting development checks and the maintainer's release workflow.

### Changed

- Replace the preliminary MaxMind integration with local ipapi.is reference data; widen city names to accommodate verified upstream values.
- Update the planned reporting design to use browser fingerprinting for estimated unique-browser counts; simplify collection documentation and remove outdated privacy claims. Fingerprinting implementation remains pending.
- Use `index.md` as the sole documentation root, require every documentation page to be reachable from it, and simplify the README to a website pointer; record these conventions in the coding guidelines.
- Document development ownership: the AI assistant handles implementation, tests, and documentation; the project owner owns architecture, all Git operations, and release scripts.
- Extend `.gitignore` for Jekyll output, caches, and local Bundler dependencies.
