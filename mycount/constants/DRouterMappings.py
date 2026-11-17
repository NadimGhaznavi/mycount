"""Router maintenance defaults."""

from typing import Final


class DRouterMappings:
    ENABLED: Final[bool] = False
    SERVICE_UNIT: Final[str] = "mycount-router.service"
    CHECK_INTERVAL: Final[int] = 300
    COMMAND_TIMEOUT: Final[int] = 30
