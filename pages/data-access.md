---
title: Data Access
author_profile: true
layout: single
---

[Documentation index]({% link index.md %})

MyCount follows the shared data access structure used by R3el and Ax3l.
Application operations belong in domain database interfaces, which use the
generic `mycount/interface/DbMgr.py` bridge. That bridge owns the MariaDB
connection, cursors, SQL execution, and transaction mechanics.

## Connection and transactions

The Python code requires Python 3.11 or later and the dependencies declared in
`requirements.txt`. `DbMgr` reads `DB_HOST`, `DB_NAME`, `DB_USER`, and
`DB_PASSWORD` from the process environment. `DB_PORT` defaults to `3306`.
The future installer will store credentials in `/etc/mycount/database.env`;
the service launcher must supply them to the process. The database manager
does not execute or load that file itself.

Each manager owns one connection and must be closed by its owner in a
`finally` block. Workers must not share a connection across threads.
Connections use UTF-8, UTC, and bounded connection and I/O timeouts.

`execute`, `insert`, and `query` accept SQL with bound parameters. Domain
interfaces own application SQL and choose which operations must succeed
together. Writes outside `transaction()` are autocommitted. A transaction
commits on success and rolls back on failure; database exceptions propagate
to the caller. `transaction(read_only=True)` supports read-only reporting.
Transactions must not be nested, and schema operations must run separately.

## Explicit schema setup

`mycount/activity/VisitorSchema.py` owns schema creation. Opening a connection
does not create or change tables. With the database already provisioned and
the credentials present in the environment, the schema entry point is:

```sh
python3 -B -m mycount.activity.VisitorSchema
```

The future install and upgrade scripts will invoke this entry point. It
creates missing tables and preserves existing records on repeated runs.
Future changes to existing tables require explicit migrations; rerunning
`CREATE TABLE IF NOT EXISTS` does not alter them.

The schema provides relational constraints and reporting indexes. Its
definition lives in the source code. Collection, fingerprint generation, and
the installation scripts remain separate work.

## Focused checks

Run these from the checkout using a Python environment with `requirements.txt`
installed:

```sh
python3 -B -m unittest discover -s tests -p 'test_db_mgr.py' -v
PATH="/usr/sbin:$PATH" python3 -B -m unittest discover -s tests -p 'test_database.py' -v
```

The first command tests database mechanics with a mocked connection. The
second starts a disposable MariaDB instance under a temporary directory,
tests the actual schema and transactions, and removes the instance afterward.
It requires `mariadb-install-db` and `mariadbd` on `PATH` and permission to
open a local listening socket. It does not use an existing database server.
These checks do not invoke Git or release scripts.
