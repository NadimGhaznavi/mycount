"""Periodically restore the public HTTP and HTTPS router mappings."""

import logging
import subprocess
from threading import Event

from mycount.interface.Network import Network
from mycount.constants.DRouterMappings import DRouterMappings
from mycount.interface.RouterMappings import RouterMappings


class MaintainRouterMappings:
    def __init__(self, router: RouterMappings) -> None:
        self.router = router

    def run(self, stopping: Event) -> None:
        logger = logging.getLogger(__name__)
        while not stopping.is_set():
            try:
                changed = self.router.forward((Network.binding("http")[1], Network.binding("https")[1]))
            except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as error:
                logger.warning("Router mapping check failed; retrying in %s seconds: %s",
                               DRouterMappings.CHECK_INTERVAL, error)
            else:
                if changed:
                    logger.info("Restored TCP router mappings for ports %s", changed)
            stopping.wait(DRouterMappings.CHECK_INTERVAL)
