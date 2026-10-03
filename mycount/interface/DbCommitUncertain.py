"""A connection failure prevented confirmation of a transaction commit."""

import pymysql


class DbCommitUncertain(pymysql.OperationalError):
    """The write may be committed; callers must not undo external effects."""
