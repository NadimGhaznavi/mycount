---
title: Release management
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

Development happens on a feature branch. The maintainer reviews and commits
changes, then runs `scripts/new-release.sh` to cut a release.

## Prepare branches

The script expects local `main`, `dev`, and feature branches. For a fresh
checkout with only `main`, create the initial branches once:

```sh
git switch -c dev
git switch -c feat/maint-0.1.0
```

Before releasing, commit all changes, bring local `main` and `dev` up to date,
and merge `dev` into the feature branch. Run the checks from the checkout:

```sh
python3 -B -m unittest discover -s tests -v
bash -n scripts/new-release.sh
```

## Cut a release

Inspect usage without changing the repository:

```sh
./scripts/new-release.sh --help
```

From the clean feature branch, choose the version and release message. For
example, the first release could be:

```sh
./scripts/new-release.sh 0.1.0 "Initial project foundation"
```

The script merges the feature branch into `dev`, records deployment impact in
`deployment/releases.json`, updates `DMyCount.VERSION` and `CHANGELOG.md`, merges
into `main`, and creates an annotated version tag.
It pushes `main`, `dev`, and the tag to `origin`, then creates the next local
feature branch, such as `feat/maint-0.1.1`.

An optional third argument sets the next feature branch name. The command
publishes Git changes; it does not install or deploy application software.

## Deployment metadata

Release preparation compares deployment artifact hashes with the previous
baseline and uses `DeploymentImpact` to record report-server, listener, and
filesystem flags. It retains the release history for upgrades that skip versions.
Removed artifacts retain their previous target associations for impact calculation.
Regenerate `DDeployment.py` with `scripts/update-deployment-dependencies.py`
after source/rule changes. Release preparation runs its `--check` before
fetching, merging, or preparing metadata; stale output must be regenerated
and committed first.
The metadata is committed with the release; do not edit its flags manually.
The release script prepares metadata after changing both the version and codename,
so the recorded hashes match the published constants. It checks dependencies again
after merging into `dev` and includes the manifest in the release commit.

The initial baseline was read from the installed 0.6.5 application. It contains
hashes only for retained installed artifacts. Unavailable source inputs, including
original systemd/Caddy templates and unretained setup scripts, have null hashes
and are treated as changed during the first release preparation. Bootstrap
records for 0.6.5 and 0.6.6 conservatively select all targets. This establishes
the history without claiming unreleased checkout files were already deployed.

Release/version-only edits do not trigger every service: hashing normalizes
only the `DMyCount.VERSION` assignment. Other constants changes remain significant.
After preparation, upgrade verifies hashes before using the recorded flags.

The release helper tests can be run independently of Git with:

```sh
.venv/bin/python -B -m unittest discover -s tests -p test_release_deployment.py -v
```
