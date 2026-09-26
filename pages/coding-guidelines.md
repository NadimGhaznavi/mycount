---
title: Coding Guidelines
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

MyCount should be easy to navigate, understand, and maintain. Each component
should have a clear responsibility, an obvious home, and a defined interface.
These guidelines describe the design goals; existing modules may still need
to be brought into this structure.

The code should be as lean as possible. Build for the requirements and behaviour that exist now, not for hypothetical future cases. Prefer the simplest design that cleanly supports the current workflow, make runtime behaviour observable, and let real usage reveal what needs to change next. Do not add abstractions, fallback paths, compatibility layers, configuration knobs, or defensive complexity unless there is a demonstrated requirement for them; when new needs emerge, extend or refactor the system then, using evidence from actual operation rather than speculation about what might someday happen.

## Respect development and release ownership

The AI coding assistant is the lead developer and handles implementation,
tests, and documentation within the architecture and standards set by the
project owner. The project owner is the architect and release manager and
owns all Git operations and releases.

The assistant must never run Git commands or release scripts. This includes
read-only Git commands and invoking release scripts indirectly through tests.
Leave those operations to the project owner.

## Classify classes by responsibility

MyCount uses a custom Common Unified Development Process as a development style.
Categorize each class by its responsibility:

| Category | Responsibility | Examples |
| --- | --- | --- |
| Interface | Bridges a technology, API, or protocol and handles the mechanics of communicating with it. | `DbMgr` for a database, `FileMgr` for files, an HTTP client |
| Activity | Performs transformations, calculations, and application operations on data. | A class that performs a calculation or coordinates an application operation |
| Entity | Stores data, whether persistent or held only in memory. | An application record or an in-memory result |

Keep these responsibilities separate to prevent monolithic classes. An
activity works on entities and uses interface classes when it needs to read,
write, or communicate with an external system. An entity representing
persistent data does not also own the database connection or persistence
mechanics.

When a class combines technology access, data transformation, and data storage,
split those responsibilities into focused collaborators. Use composition to
connect them rather than growing one class to do everything. Classification
describes a class's role; it does not require a shared base class or an
inheritance hierarchy.

Here, **interface class** means a technology bridge. Elsewhere in this document,
an interface can also mean a component's public contract; having public methods
alone does not make a class an interface class.

## Organize code by responsibility

Group related components under `mycount/`:

| Package | Responsibility |
| --- | --- |
| `app/` | Application logic and workflows |
| `activity/` | Shared activities such as schema setup and event preparation |
| `entity/` | Application records and results |
| `server/` | Server entry points and orchestration |
| `interface/` | Interfaces to external services and application components |
| `constants/` | Shared application constants |

Add packages when a responsibility needs its own home. Keep the structure
focused on the functionality MyCount actually uses.

Give each major class its own module, named after the class. Small supporting
types and private helpers may stay with the component they serve.

Prefer explicit imports from the owning module, for example:

```python
from mycount.constants.DMyCount import DMyCount
```

Keep presentation code and its assets together, separate from application
logic. Keep package initializers small. Use `__main__.py` when a package needs
to be executable, and keep documented entry points working during refactors.

## Name constants consistently

Group related constants in classes prefixed with `D`, under `mycount/constants/`.
Name each module after its class, such as `DMyCount.py` containing `DMyCount`.
Use uppercase names with `Final` type annotations for constant values, and
access them through the class, for example `DMyCount.VERSION`.

## Separate application meaning from implementation mechanics

Application code should call an interface that expresses its intent. That
interface translates the request into operations on a lower-level helper.
Callers should not bypass the interface or reach into the helper's resources.

Keep generic helpers independent of MyCount rules and schema details. Keep
application decisions in the layer that understands MyCount. Use composition
to make that relationship explicit.

## Trust internal contracts

When using LLMs, supply task data as JSON, separate from the prompt instructions. Simplify
the data before presenting it: sort file lists and assign sequential numeric IDs,
keeping exact paths and ID mappings on the server. Use deterministic code for
bookkeeping and reserve the LLM for interpretation.

MyCount's internal modules are developed and maintained together. Use clear
interfaces, type annotations, and tests to establish their contracts. Do not
add runtime type checks, attribute-existence checks, repeated validation, or
fallback paths merely to defend against another internal module being used
incorrectly.

Validate external inputs at their entry points, such as configuration files,
incoming messages, and decoded database results. Once data has been validated
and converted into application objects, internal callers should use those
objects directly without rechecking the same contract at every layer.

Let internal programming errors surface clearly, even if they stop the
application. Fix the root cause and add a regression test. Do not hide bugs
with broad exception handlers, silent defaults, coercions, or speculative
recovery code intended to keep execution going.

Keep resource cleanup and transaction rollback reliable while allowing the
failure to propagate. Handle expected external failures at the responsible
boundary, preserving their cause. These responsibilities do not justify
defensive scaffolding around trusted internal calls.

## Use a shared data access layer

Apply this guidance if the application needs database access; do not introduce
a database before there is a requirement for one.

Application components that access MariaDB must use the shared data access
layer. `DbMgr` alone owns connections, cursors, SQL execution, and transactions.
Domain database interfaces own application queries and call its generic SQL
methods; application code calls named operations on those interfaces.

The application interface owns:

- MyCount table names, column mappings, and application queries.
- Conversion between application values and persisted representations.
- Decisions about which operations must succeed together in one transaction.

The database helper owns:

- MariaDB connection creation, credentials, timeouts, and connection cleanup.
- Cursor creation, use, and cleanup. Cursors never escape this layer.
- Generic SQL execution and bound values; application queries and any dynamic identifier validation remain in the owning database interface.
- Transaction execution: begin, commit, rollback, and read-only transactions.
- Consistent result handling and database errors that preserve their causes.

Let database errors leave the transaction block so the database helper can
roll back and report them. Handle them outside the block; do not swallow an
error and continue issuing statements inside the same transaction. Rely on
MariaDB's row locks and constraints rather than adding duplicate consistency
checks.

The database helper must not know application rules. Application components
must not create separate connection or SQL execution mechanisms.

Keep application side effects explicit. Opening a database connection must
not trigger unrelated application operations.

## Keep configuration validation behind one interface

Resolve external configuration through one application interface before
passing it to internal components. That interface owns application rules and
returns a complete configuration or raises a clear error. Internal components
use the resolved configuration without validating it again.

If schema validation needs a generic helper, keep it independent of MyCount
rules and behind the configuration interface.

Resolving a configuration must not mutate the caller's data or share mutable
defaults between resolutions. Keep validation errors specific enough to
identify the field that failed.

## Refactor in reviewable steps

Make one coherent structural change at a time. Preserve behavior when moving
or renaming components, and treat behavior changes as separate work.

For each move, update imports, relevant test references, resource paths, and
deployment file lists and copying rules. A module that works in the source
checkout must also be included in the installed application.

Run the tests relevant to the change. For changes to layer boundaries, verify
contracts such as transaction atomicity, rollback, resource cleanup, error
translation, and use of shared interfaces. Check entry points and asset
loading when converting a module into a package.

Distinguish new failures from existing failures. Report verification limits
clearly, including when live database integration has not been tested.

## Keep documentation focused

Use `index.md` as the sole documentation root. Keep `README.md` as a pointer
to [mycount.osoyalce.com](https://mycount.osoyalce.com), without duplicating
documentation or navigation there.

Every documentation page must be reachable by following links from `index.md`,
either directly or through another reachable page. No orphaned pages. When
adding or moving a page, update the navigation links so it remains reachable
from the root.

Give each guide one purpose and an accurate title. Document implemented behavior
and verified commands. Add installation, configuration, running, and uninstall
guides when those workflows exist, keeping each in its own page.

## Update the CHANGELOG.md

Update the CHANGELOG. If there are many low level changes, then include a `### Summary` 
section below `## [Unreleased]` that includes a short summary of the changes. The summary should outline the problem and solution in one or two sentences. E.g. *"This fixes the Event Log flicker."* or *"Add a new age plot on the existing demographic plot."*.
