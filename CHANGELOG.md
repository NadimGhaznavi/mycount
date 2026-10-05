---
title: Changelog
author_profile: true
layout: single
permalink: /CHANGELOG/
---

# Changelog

## [Unreleased]

## [1.5.4] - 2026-10-05 @ 18:38

- Restore deployment metadata preparation and dependency checks in the release
  script, repair the missing 1.5.3 deployment baseline, and identify version
  mismatches in upgrade errors.

## [1.5.3] - 2026-10-05 @ 18:34

- Add CMDB scanner metadata: subtype `Web Analytics`, supplier `Nadim-Daniel`,
  and codename `Insight`.
- Updated `scripts/new-release.sh` script.

## [1.5.2] - 2026-10-04 @ 19:52

- Make all Metrics boxes collapsible and collapsed by default, and move Recent
  Visits pagination links to the right of its title bar.

## [1.5.1] - 2026-10-04 @ 19:40

- Expand all pie charts and legends to 11 Mondrian colors with dark and
  darker red, blue, and yellow shades, plus matching slice outlines.

- Show readable language names in the Visits by Language legend and hover
  text, including country and script names. Preserve unrecognized tags and
  keep regional preferences separate.

## [1.5.0] - 2026-10-04 @ 19:32

- Split the location pie chart cell into Visits by Location and Visits by
  Language, using each visit's first browser language preference and the
  current report filters. Include missing preferences as Unknown.

## [1.4.1] - 2026-10-04 @ 19:09

- Allow `https://bmgeoip.osoyalce.com` and `https://bmdynip.osoyalce.com`
  to submit page views to the collector.

## [1.4.0] - 2026-10-04 @ 07:15

- Add a MyCount event to track system events.

## [1.3.1] - 2026-10-04 @ 05:52

- Add sidebar content.

## [1.3.0] - 2026-10-03 @ 21:00

- Add a background UPnP worker that checks TCP ports 80 and 443 every five
  minutes, repairs missing or incorrect mappings, and retries router failures.
  Preserve correct mappings, bound router commands with timeouts, and manage
  the worker during installation, upgrades, and uninstall.

## [1.2.0] - 2026-10-03 @ 16:55

- Refresh the documentation site's client example with a build-versioned script
  URL, the site counter, and current payload verification instructions; document
  the `/get_count` Caddy route and publication of updated client assets.
- Remove the date-range and pagination hint from Report Filters.
- Remove the Report Filters timezone control and automatically use the browser's
  local timezone for report dates and marketing chart posting times, including
  when following report links from another timezone.

## [1.1.0] - 2026-10-03 @ 16:19

### Summary

Preserve marketing screenshots when a save may already have committed and make
retries confirm the same posting. Bound control reports by date range, paginate
recent visits, and move report orchestration into an activity.

- Distinguish uncertain database commits, retain affected screenshots, and use
  unique marketing submission IDs to prevent duplicate retry effects.
- Add explicit reconciliation for old unreferenced screenshots, preserving
  referenced files and recent uploads.
- Default reports to 30 local calendar days, allow ranges up to 366 days, and
  paginate recent visits in groups of 50 using receipt time and record ID.
- Query daily chart aggregates using timezone-aware UTC day boundaries instead
  of loading every visit timestamp into the browser.
- Move report queries, snapshot transactions, and connection cleanup to
  `ReadReports`; keep filters and pagination in the report URLs.

- Add `scripts/clear-upnpc-routes.sh` to clear MyCount's TCP port 80/443 router
  mappings and matching UDP destinations, verify removal, and preserve other
  ports and unmatched UDP mappings.
- Invoke router cleanup during uninstall before removing application files;
  stop file removal if cleanup fails.

## [1.0.0] - 2026-10-03 @ 15:22

### Summary

Use BMGeoIP for geolocation and detect the deployment host when routing public
traffic, so MyCount can be installed on wintermute without local GeoIP datasets.

- Query BMGeoIP at `geoip.osoyalce.com:54300`, validate its response, and preserve
  location snapshots and overlapping-range selection. Service failures return 503.
- Remove local GeoIP import code and refresh scheduling; retain visitor data and
  remove legacy schedules during full setup.
- Discover the install host through UPnP, replace TCP port 80/443 mappings, and
  verify that both mappings point to the detected host.
- Restore alphabetical platform ordering, including Discord.
- Tighten marketing form, URL, Origin, and request framing validation.

## [0.14.2] - 2026-10-03 @ 04:55

- Smooth the Marketing visits line with Plotly spline interpolation.

## [0.14.1] - 2026-10-03 @ 04:53

- Added *Discord* platform.

## [0.14.0] - 2026-10-03 @ 04:45

- Attach optional PNG screenshots to promotional posts, store files in the server's `pages/marketing` folder, and display them from the event details or chart marker. Preserve existing events with a nullable screenshot reference, retain uploads through upgrades and uninstall, and remove new files if saving fails.
- Add a simple Marketing form for promotional posts with browser-local posting time, alphabetized platforms, posting URL, and notes; store posting events in UTC with system-generated creation timestamps.
- Plot daily total visits on Marketing with vertical posting markers and a bot filter, alongside the saved posting details.
- Show the creator's GitHub account in the documentation author profile.
- Remove brackets from the top-right navigation, hide the current page's link, and add a blank Marketing page.
- Added mycount site name to the `_config.yml`.

## [0.13.2] - 2026-10-01 @ 03:05

- Increase the bottom chart content height to 300px, with a taller Visits by Site pie and legend.

## [0.13.1] - 2026-10-01 @ 03:02

- Show Visits by Site legend items on one line as `site - visits (23%)`, rounding percentages to whole numbers for this chart only.

## [0.13.0] - 2026-10-01 @ 02:56

- Use Mondrian chart colors with brighter 4-pixel bar and pie outlines, and render the location pie with Plotly.
- Add a Visits by Site pie beside All Traffic at the bottom of Metrics, occupying one third of the row and stacking on small screens.

## [0.12.0] - 2026-10-01 @ 02:40

- Add a compact, full-width Plotly bar chart titled All Traffic at the bottom of Metrics, showing daily hits across all sites in browser-local time, including zero-traffic days and respecting the bot filter.

## [0.11.1] - 2026-09-30 @ 17:37

- Populate Counting since from the earliest recorded visit on Metrics and Reference, using the browser's local date and keeping it independent of the bot filter.
## [0.11.0] - 2026-09-30 @ 17:29

- Add a sortable Referrers table in the right column, grouped by host with visit totals, Direct / Unknown visits, bot filtering, and a 10-row scroll area.
- Move the Visits by Location pie chart above the location table.

- Limit Recent Visits and Visits by Location to a 10-record viewport with scrolling, and load all matching recent visits instead of only the latest 20.

- Add “Counting since September XX, 2026” beneath MyCount Control in the title box.

## [0.10.0] - 2026-09-28 @ 12:32

- Add a Visits by Location country pie chart below the location table, with visit counts, percentages, and the existing bot filter.

## [0.9.1] - 2026-09-27 @ 17:44

- Prefix country names in Visits by Location with Unicode flags while preserving country-name sorting.
- Prefix cities in Recent Visits with Unicode country flags, retaining city-name sorting and omitting flags for unknown countries.
- Add City between Time and URL in Recent Visits, displaying `---` for unknown cities.

## [0.9.0] - 2026-09-27 @ 17:38

- Add Recent Visits below Visits by Site with the latest 20 matching visits, newest first, browser-local dates, 12-hour times, and URLs. Apply the existing bot filter.

## [0.8.0] - 2026-09-27 @ 16:36

- Add a read-only, bot-filtered `/get_count?site=...` endpoint and optional `data-mycount-counter` elements in the shared client. Fetch once after tracking, reuse the count across elements, and show an em dash on failure without retrying or recording extra visits. Route the endpoint through Caddy.

## [0.7.3] - 2026-09-27 @ 16:24

- Add a Filters box with Exclude bots enabled by default, consistently filtering site/page/location counts, last-visited times, and totals. Include historical GoogleOther/Googlebot records in exclusion and correctly flag new GoogleOther visits as bots.
- Fix country-name backfill timeouts by scanning primary keys in bounded batches and committing each batch independently. Log progress and preserve completed updates on retry.

## [0.7.2] - 2026-09-27 @ 16:06

- Store CSV country names in GeoIP ranges and visits; backfill missing historical names from ISO codes using pycountry. Display full country names while retaining country codes for grouping.
- Remove Continent from the location report, collection, and both database schemas; upgrades drop the old columns while preserving visits and ranges.

## [0.7.0] - 2026-09-27 @ 15:56

- Add bold, right-aligned total rows to the site and location tables, kept at the bottom when sorting.
- Rename Sites to Visits by Site and add a sortable Visits by Location table alongside it, with continent, country code, state/province, city, and visit totals. Show unknown locations as `---` and stack the tables on narrow screens.

## [0.6.11] - 2026-09-27 @ 14:44

### Added

- Store the request's full IPv4 or IPv6 address with each new page view. Add a nullable IP column for existing databases, preserving unknown historical addresses.
- Retain page query strings separately from page URLs, store the full browser-provided HTTP(S) referrer, and import/copy GeoIP continent values with nullable schema migrations.
- Import optional GeoIP latitude/longitude, ZIP/postal code, and timezone and retain them with new visits. Validate coordinates and field lengths, preserve postal-code leading zeros, keep the browser timezone separate, and add nullable schema migrations.

### Changed

- Format Last refresh as `MMM DD - HH:MM` in browser-local time.
- Consolidate Reference into one Visitor Data inventory with Source, Source Details, Table, Column, and Details; include optional browser fields, all GeoIP CSV fields, and explicit markers for values not stored.
- Limit Visitor Data to external browser, request, and GeoIP inputs, sorted by Source and then Source Details.
- Update the collection documentation and Reference storage mappings for the new fields.

### Removed

- Remove the unused region-code field from collection and reference documentation; upgrades drop its database column while preserving visits and region names.
- Remove internal identifiers, derived values, protocol metadata, and the hypothetical IP-hash entry from the Reference inventory.
- Remove obsolete tracking placeholders and the browser identity documentation section.

## [0.6.9] - 2026-09-27 @ 13:50

- Add Metrics and Reference navigation to the report server, show the collection tables and optional browser fields on Reference, move Last refresh below the header, and enable column sorting for metrics.
- Document collected page-view data, optional browser details, storage locations, and browser ID behavior in a linked data inventory.

## [0.6.8] - 2026-09-27 @ 13:06

- Extract portable, standard-library deployment tooling with project-supplied configuration. Generate `DDeployment.py` from source scans and explicit MyCount rules; require a nonmutating freshness check during release preparation. Document the reusable boundary and maintenance workflow.
- Shorten the deployment dependency guide for DevOps and document the portability boundary and planned dependency generator.
- Refactor deployment into explicit stages selected by impact flags. Limit service-only file copies and removals to affected targets, skip deployment stages for no-impact releases, and publish installed release metadata only after successful completion.
- Record deployment-impact flags during release preparation and combine them across skipped releases during upgrades. Report-only releases restart only the control service; filesystem/setup changes use the full deployment workflow.
- Add an initial installed-artifact baseline and preserve the last successful deployed version for retrying failed upgrades. Reject unprepared deployment files before stopping services.
- Add `DeploymentImpact` to check whether an artifact affects a deployment target through direct or transitive dependencies, and list all affected targets.
- Require deployment dependency updates alongside relevant code and asset changes, prominently in the Coding Guidelines.
- Define static file dependency graphs for the report server, listener, and filesystem/setup targets in `DDeployment`, as the foundation for selective deployment decisions.

## [0.6.6] - 2026-09-27 @ 12:12

- Expand site rows to show per-page visit counts and last-visited times, ordered by most visits first with URL order breaking ties.

## [0.6.5] - 2026-09-27 @ 12:02

- Show per-site visit totals and latest visit times in MyCount Control, with browser-local timestamps and a title-bar last-refresh time. Load database credentials for the control service.

## [0.6.2] - 2026-09-27 @ 11:52

- Add a standalone `mycount-control` service on port 61777 with a dark orange banner styled after R3el. Install and upgrade deploy and health-check both services; uninstall removes both.

## [0.6.0] - 2026-09-27 @ 09:46

- Count unique browsers per site using a persistent random first-party local-storage ID. Keep collecting unidentified page views when storage is blocked, and preserve historical rows without inventing visitor identities.
- Add per-site totals for page views, unique browser IDs, unidentified views, and known bot views; document rollout and counting limits.

## [0.5.0] - 2026-09-27 @ 09:35

### Summary

Record referring sites and richer visitor details alongside existing city,
region, country, and language data. Preserve historical visits and accept older clients during rollout.

- Add referrer hostname, retained user-agent, browser/OS versions, device brand/model, and bot classification.
- Collect optional screen, timezone, hardware, connection, navigation, and browser preference details with bounded validation.
- Add repeatable schema migration and document collector-first deployment and referrer/city reporting.

## [0.4.2] - 2026-09-27 @ 08:39

- Allow `https://r3el.osoyalce.com` to submit page views to the collector.

## [0.4.0] - 2026-09-27 @ 08:01

- Added a bunch of allowed sites.

### Added

- Add an Ax3l HTTPS smoke test for health, CORS preflight, and one identifiable test visit, with an optional local Caddy mode.

## [0.3.0] - 2026-09-27 @ 07:19

### Added

- Add an upgrade script that reuses deployment, validates retained credentials before stopping the collector, and preserves GeoIP data instead of repeating the import.
- Allow MyCount and Ax3l through a configurable origin allowlist; accept validated client site labels and require page URLs to match the requesting origin.

### Changed

- Update the client example to display its configured `/count` endpoint and explain how to verify that a page view was stored.

## [0.2.0] - 2026-09-27 @ 07:03

### Added

- Add a repeatable uninstaller and removal guide; preserve collected data, credentials, accounts, and shared services and router mappings.
- Add isolated deployment tests for repeated installation/removal, Caddy preservation, validation failures, and reload rollback.

### Changed

- Show installation stages and GeoIP download/import progress so the initial data load no longer appears stuck after dependency installation.
- Check Python and deployment prerequisites, stop the collector before dependency updates, and verify collector health before configuring HTTPS.
- Validate Caddy with relative imports anchored to its configuration directory and restore previous configuration files if service activation or reload fails.
- Add Caddy setup preserving existing sites, public certificate automation, and UPnP forwarding; accept validated visitor addresses from the local proxy for geolocation.
- Use standard HTTPS port 443 with `/count` for collection; keep port 36666 local, forward router ports 80/443, and update the browser endpoint and installation guide.
- Document the complete Caddy configuration, import placement alongside the LAN-only site, validation and reload commands, and public HTTPS verification.

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
- Use `index.md` as the sole documentation root, require every documentation page to be reachable from it, and simplify the README to a website pointer; record these conventions in the coding guidelines.
- Document development ownership: the AI assistant handles implementation, tests, and documentation; the project owner owns architecture, all Git operations, and release scripts.
- Extend `.gitignore` for Jekyll output, caches, and local Bundler dependencies.
