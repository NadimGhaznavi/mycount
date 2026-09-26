---
title: Changelog
author_profile: true
layout: single
permalink: /CHANGELOG/
---

# Changelog

## [Unreleased]

### Summary

Establish the MyCount documentation website and development foundation, with
shared coding conventions and a tested release workflow.

### Added

- JavaScript page-view client and Jekyll example targeting `https://count.osoyalce.com/`, recording the visited URL's origin and path without query strings or fragments, browser language and user-agent metadata, no cookies or persistent identifiers, and a linked integration guide describing the service contract and privacy boundaries.
- Project mission documenting the mydynip testing purpose, planned visitor metrics, browser and service components, and privacy boundaries, linked from the homepage.
- Jekyll configuration for `mycount.osoyalce.com` using the dark Minimal Mistakes theme.
- Minimal homepage linking coding guidelines, release management, and the changelog.
- `AGENTS.md` and MyCount coding guidelines covering component responsibilities, constants naming, and focused documentation.
- Python package foundation with `DMyCount.VERSION`, initially `0.0.1`.
- Release script that updates the version and changelog, merges feature work through `dev` to `main`, and publishes an annotated tag.
- Six isolated release tests covering successful publication, prereleases, invalid input, dirty working trees, duplicate versions, and help output.
- Release guide documenting development checks and the maintainer's release workflow.

### Changed

- Use `index.md` as the sole documentation root, require every documentation page to be reachable from it, and simplify the README to a website pointer; record these conventions in the coding guidelines.
- Document development ownership: the AI assistant handles implementation, tests, and documentation; the project owner owns architecture, all Git operations, and release scripts.
- Extend `.gitignore` for Jekyll output, caches, and local Bundler dependencies.
