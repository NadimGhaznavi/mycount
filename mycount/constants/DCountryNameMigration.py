"""Bound the work and transaction size of country-name backfills."""

from typing import Final


class DCountryNameMigration:
    BATCH_SIZE: Final[int] = 1000
