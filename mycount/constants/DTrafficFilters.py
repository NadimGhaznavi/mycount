"""Report filter modules and their presentation labels."""

from typing import Final


class DTrafficFilters:
    NONE: Final[str] = "none"
    BASIC: Final[str] = "basic"
    ISOFOREST_PLUS: Final[str] = "isoforest_plus"
    DEFAULT: Final[str] = ISOFOREST_PLUS
    OPTIONS: Final[tuple[tuple[str, str], ...]] = (
        (NONE, "None"), (BASIC, "Basic Bots"), (ISOFOREST_PLUS, "IsoForest+"),
    )
    MODULES: Final[dict[str, tuple[str, ...]]] = {
        NONE: (), BASIC: (BASIC,), ISOFOREST_PLUS: (BASIC, "isoforest"),
    }
