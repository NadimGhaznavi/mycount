"""Periodically restore the public HTTP and HTTPS router mappings."""

import logging
import subprocess
from threading import Event

from mycount.constants.DCaddy import DCaddy
from mycount.constants.DMyCount import DMyCount
from mycount.constants.DRouterMappings import DRouterMappings
from mycount.interface.RouterMappings import RouterMappings


class MaintainRouterMappings:
    def __init__(self, router: RouterMappings) -> None:
        self.router = router

    def run(self, stopping: Event) -> None:
        logger = logging.getLogger(__name__)
        while not stopping.is_set():
            try:
                changed = self.router.forward((DCaddy.HTTP_PORT, DMyCount.HTTPS_PORT))
            except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as error:
                logger.warning("Router mapping check failed; retrying in %s seconds: %s",
                               DRouterMappings.CHECK_INTERVAL, error)
            else:
                if changed:
                    logger.info("Restored TCP router mappings for ports %s", changed)
            stopping.wait(DRouterMappings.CHECK_INTERVAL)
