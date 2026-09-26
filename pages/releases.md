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

The script merges the feature branch into `dev`, updates `DMyCount.VERSION`
and `CHANGELOG.md`, merges into `main`, and creates an annotated version tag.
It pushes `main`, `dev`, and the tag to `origin`, then creates the next local
feature branch, such as `feat/maint-0.1.1`.

An optional third argument sets the next feature branch name. The command
publishes Git changes; it does not install or deploy application software.
