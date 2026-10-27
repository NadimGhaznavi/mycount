---
title: DB Server Component
lang: en
locale: en-US
language_name: English
component_id: "bmforge.db-server"
spec_version: "0.4.0"
spec_status: "draft"
translation_key: bmforge-component-db-server
---

**Component ID:** `{{ page.component_id }}` · **Specification:** `{{ page.spec_version }}` ({{ page.spec_status }})

This contract follows the [engineering policy]({{ site.baseurl }}{% link pages/engineering-contract.md %}), [health check contract]({{ site.baseurl }}{% link pages/health-checks.md %}), and [traceability rules]({{ site.baseurl }}{% link pages/specification-lifecycle.md %}).

## Intent and scope

Provide a minimal application-owned database service layer backed by MariaDB using PyMySQL. This is application-side data access, not a managed MariaDB daemon. Separate connection/SQL execution mechanics from application schema and queries. Do not introduce an ORM, global connection pool, migration framework or remote service without a concrete requirement.

## Approved runtime modules

This is the **complete approved module inventory for the canonical, reusable `DbMgr.py`** in specification `0.4.0`.

| Origin | Module | Purpose |
| --- | --- | --- |
| Python stdlib | `contextlib` | `contextmanager` for transaction commit and rollback |
| Third-party | `pymysql` | MariaDB connection, bound SQL, queries, and transactions |
| Third-party submodule | `pymysql.cursors` | `DictCursor` for dictionary result rows (part of PyMySQL, not another package) |

**Approval boundary:** The canonical `DbMgr.py` is **copied unchanged** into each application using MariaDB; its methods, imports and class name are not customized. Supply application configuration at construction, and create separate `*Db` domain interface classes for application SQL. Codex **must pause and ask the user** before adding, removing, or replacing an approved infrastructure module or changing `DbMgr.py`. User-approved changes belong in a revised BMForge specification before adoption.

These are Python import modules, not a complete transitive dependency tree. The consuming application's dependency file records installed package versions. Application business logic and separately selected BMForge components are outside this list; they must not quietly change this component's technology choices.

**Database technology:** MariaDB. Do not substitute PostgreSQL, SQLite, SQLAlchemy, Peewee, mysql-connector, an ORM, an alternate driver, or an application-external database service. A different database backend is a new component specification requiring user approval.

**Not part of the generic manager:** `GeoIpDb`, `VisitDb`, `MiningDb`, `GeoIpSource`, schema definitions, and application-specific SQL. They belong in the consuming application's **domain interface** classes. See [Activity / Interface / Entity Classification]({{ site.baseurl }}{% link pages/classification.md %}).

## Canonical implementation and layered DAL

**Every new MariaDB-backed application copies the same file, unchanged:**
`components/templates/db-server/interface/DbMgr.py` → `<app>/interface/DbMgr.py`.

The application's configuration interface resolves secrets, connection details and timeouts and passes them as constructor keyword arguments. **Do not import application constants, schema or environment readers inside the canonical manager.** It has generic `execute`, `insert`, `execute_many`, `query`, `transaction(read_only=False)`, `health`, and `close` methods, plus context-managed cleanup.

Above `DbMgr`, the app defines one or more **domain database interface classes**, such as `VisitorDb`, `MiningDb`, or `GeoIpDb`. Each takes a `DbMgr` instance through its constructor. They own SQL, schema, row-to-entity translation, and grouped writes. They never call `pymysql.connect` or manage cursors directly. Multiple domain classes may share a single `DbMgr` within one owning worker/transaction, **not across threads**. Database provisioning and business data migrations remain separate operations.

For example, a consumer may implement:

```python
class VisitorDb:
    def __init__(self, db: DbMgr):
        self._db = db

    def count(self):
        return self._db.query("SELECT COUNT(*) AS visits FROM page_views")[0]["visits"]
```

An `activity/CollectVisit.py` class calls named `VisitorDb` operations and works on an `entity/Visit.py` value. No SQL lives in activities, entities, templates or HTTP/ZeroMQ transport. This arrangement uses plain composition, not inheritance or an ORM. See the [classification contract]({{ site.baseurl }}{% link pages/classification.md %}).

**New project integration:** copy `DbMgr.py` unchanged, pass the resolved configuration, write only the required domain `*Db` interfaces and entities, and test the application transaction and health paths. Existing applications do not require an automatic migration merely because this draft specification has changed.

## Reference snapshot

- `components/reference/bmgeoip/bmgeoip/interface/DbMgr.py`: historical version of the mechanics, **not** the copyable canonical file (it imports BMGeoIP constants)
- `components/reference/bmgeoip/bmgeoip/interface/DatabaseEnvironment.py`: BMGeoIP-specific configuration loading; new apps resolve their own settings separately
- `components/reference/bmgeoip/bmgeoip/interface/GeoIpDb.py`: application SQL and schema owned by a domain interface
- `components/reference/mycount/mycount/interface/VisitDb.py`: another domain interface using `DbMgr`, pinned from MyCount commit `90574cd838ba43499a825c6a193b43cbc485c91c`

## Required contract

- The **unchanged canonical `DbMgr.py`** owns one MariaDB connection, created from resolved application configuration and closed deterministically. The application provides its DB host/port or socket, schema name, credentials and timeouts when constructing it. Never share one manager instance between worker threads.
- Resolve and validate external connection configuration in an application interface **before** constructing `DbMgr`; do not add configuration-file parsing or application-specific constants to the manager. No credentials in source, public documentation, status messages or HTTP output.
- Use utf8mb4, dictionary results as needed, explicit connect/read/write timeouts, and strict SQL mode consistent with the reference implementation.
- Use the canonical methods: parameterised `execute`, `insert` (generated ID), `execute_many`, `query`, `transaction(read_only=False)`, `health` and `close`. All SQL and dynamic identifier allowlists live in the application's `*Db` interfaces, not the manager. Use driver-bound parameters for data values.
- Transaction context commits only on success and rolls back on exceptions, preserving the original exception even when rollback also fails. DDL and schema creation are handled separately from multi-statement data transactions.
- The application's **interface/** domain `*Db` classes own SQL schema, indexes, constraints, read/write methods, row/entity mapping and atomic write workflows. `activity/` uses their named operations and `entity/` stores the data. **Never import GeoIpDb or create GeoIP tables** for an unrelated application.
- Offer a small application-internal, read-only health operation using the **application's configured database connection** (for example `SELECT 1` via its DB manager). It reports failure when the app cannot use that connection; do not catch and suppress errors, reconnect automatically, or create a special monitoring connection. The application's health handler reports this result to CMDB; **CMDB must not connect to MariaDB directly for DB Server health**.
- Use `CMDB_DATABASES` declarations for app discovery and follow BMForge runtime configuration and deployment guidance. An inventory declaration does not create database users, schema or backups automatically.
- Explicitly choose the consistency and concurrency contract for each application's writes. For a time-tracking service, consider idempotent event IDs and transactional session transitions only when those behaviours are part of its own requirements.

## Acceptance checks

1. Connect with a dedicated test database and credentials; missing/bad credentials fail without exposing passwords.
2. Bound insert/query round trip works, including Unicode and parameterised values; injection-like input is stored as a value.
3. Multiple writes commit atomically; an injected failure rolls all writes back and rethrows.
4. Separate worker threads use separately owned connections; closure releases resources.
5. Invalid/missing configuration and a database outage yield explicit errors and do not leave a partially reported success.
6. Application-internal DB health succeeds while the app can query through its own connection, fails on a simulated outage, and causes the application's aggregate `/health` to become unhealthy; no direct CMDB-to-MariaDB connection is used.
7. Only the new application's schema and SQL are present; no BMForge/bmgeoip runtime imports. Verify CMDB declarations agree with deployment.
8. Verify `<app>/interface/DbMgr.py` is an unchanged copy of `components/templates/db-server/interface/DbMgr.py`, with `BMFORGE_COMPONENT` version `0.4.0`. No application SQL, constants or domain names belong in the manager.
9. Verify each `*Db` domain interface delegates SQL execution and transactions to its injected `DbMgr`, while activities and entities have no direct PyMySQL access.
10. Verify the DB Server uses only approved modules and MariaDB; any infrastructure change must be approved by the user before updating this component specification.
