---
title: IsoForest Traffic Filtering
layout: single
author_profile: true
---

## Report filters

Map, Metrics, Marketing, and Visitors share three filter choices:

| Filter | Behavior |
| --- | --- |
| None | Apply neither bot-detection method. |
| Basic Bots | Use the existing browser, automation-profile, and stored bot classifications. |
| IsoForest+ | Exclude visits flagged by either Basic Bots or the latest completed IsoForest run. This is the default. |

IsoForest processes every collected page view, including known bots and test
traffic. Basic Bot classifications never enter its training features. Existing
report rules for test traffic apply when reports are read; Visitors continues
to expose stored records through its column filters.

Model decisions are stored separately from `page_views.is_bot`. Filtering
changes report queries, not the collected records. Date ranges, totals,
charts, and pagination use the selected filter. Existing `exclude_bots=0` and
`exclude_bots=1` bookmarks still work; new links use `filter=none`,
`filter=basic`, or `filter=isoforest_plus`.

The browser remembers the selected filter, site, date range, and timezone for
the session as you navigate between report pages. Explicit URL parameters
override remembered settings. Visitors shares the traffic filter while its
column searches remain separate; pagination positions are never remembered.

Each report selects one completed run inside its database snapshot. New or
otherwise unassessed visits remain visible until a later run. Before the first
completed run, IsoForest+ applies Basic Bots and displays that model results
are unavailable. A failed run leaves the previous completed results active.

## Runs and schedule

Open **IsoForest** in the web navigation to inspect run history, model settings,
and up to 100 observation groups from a selected run. The evidence table shows
anomalies first, ordered by lowest decision score. Expand **Inspect** to see
the numeric features. Scores below zero are anomaly candidates; they are not
bot probabilities. A group's decision applies to all visits represented by it.

The default schedule is `0 * * * *`: once each hour in the server's local
timezone. Enter a five-field cron expression and click **Update schedule** to
change it. Disable **Enabled** to stop recurring runs. Settings survive upgrades.
The first enabled check initializes results when no run has been recorded.

**Queue run** requests work on the next minute check. Queued requests work even
with the recurring schedule disabled. Reload the page to see the result.
Training never runs inside an HTTP request, and overlapping workers do not run
against the same installation.

Installation supplies a root-owned `/etc/cron.d/mycount-isoforest` entry that
starts `mycount-isoforest.service` each minute. This short-lived systemd job
loads the existing protected database environment and runs as the MyCount
service user. The application checks the saved schedule before loading the ML
runtime. No credentials or user-supplied commands appear in cron.

For an immediate operational check from the installed host:

```sh
sudo systemctl start mycount-isoforest.service
sudo journalctl -u mycount-isoforest.service
```

Starting the service honors the saved schedule and queued request. Use the
web **Queue run** action when a run is needed outside its recurring schedule.
Installation and upgrades apply the schema explicitly and stop the worker
before replacing code. Uninstall removes the job and cron entry while
preserving the database, including model-run history.

## Feature and model definition

`DIsoForest` holds the tunable implementation constants: feature version,
network prefixes, observation window, feature order, and random seed. The
initial version is `network-rotation-v2`, using IPv4 `/16` blocks, IPv6 `/48`
blocks, and fixed 24-hour UTC windows. Report dates and displayed timestamps
continue to use browser-local time.

One observation describes a site within a network block and time window.
Each distinct IP contributes its median visit timestamp and modal path,
browser profile, and user-agent. This reduces the influence of a long browsing
session from one address while retaining every visit in its group's membership.
Missing IP addresses form separate observations rather than one shared network.

Eleven features describe address and subnet spread, cross-site network activity,
path/profile/user-agent diversity across IPs, and inter-IP timing. IPv6 uses
`/56` and `/64` subnets for the features named after IPv4 `/20` and `/24`
subnets. IP identities, site identities, country identities, UUIDs, and Basic
Bot decisions are not feature values.

The pipeline uses scikit-learn `IsolationForest` with its automatic cutoff and
seed 42. Each run fits and scores the complete collected history. Its manifest
records feature names/version, library versions, network/window settings, and
estimator parameters. Changing the model or representation requires an explicit
version change and, when columns change, an explicit schema migration.

## Stored evidence and operating cost

| Table | Contents |
| --- | --- |
| `isoforest_runs` | Run status, source coverage, model/feature metadata, counts, elapsed time, and serialized fitted model. |
| `isoforest_observations` | Network/site/window groups, typed numeric features, scores, and anomaly decisions. |
| `isoforest_observation_visits` | Membership mapping each assessed visit to exactly one observation in a run. |

Observation evidence, memberships, and completion status publish in one
transaction. Incomplete or failed runs cannot become the active report filter.
Run history and evidence are retained in the database; each run adds one
membership per collected view and one row per observation. Processing and
storage therefore grow with both traffic history and the number of runs.

On the development machine, the 3,211-view production snapshot produced 1,999
observations. Model fitting and scoring took approximately 0.38 seconds, with
about 145 MiB peak process memory; reading inputs, constructing features, and
imports add time. These measurements describe that dataset and development
host. Use the recorded run counts and elapsed times to adjust the schedule as
the database grows.

The supplied snapshot reproduced 503 report views under IsoForest+, compared
with 689 under Basic Bots. For the blog on November 6–12, 2026, Toronto time,
IsoForest+ retained 18 of the 133 views kept by Basic Bots. These are retained
page-view counts, not verified human counts.
