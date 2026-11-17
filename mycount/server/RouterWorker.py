"""Run router maintenance independently of the HTTP workers."""

import logging
import signal
from threading import Event

from mycount.activity.MaintainRouterMappings import MaintainRouterMappings
from mycount.constants.DRouterMappings import DRouterMappings
from mycount.interface.RouterMappings import RouterMappings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not DRouterMappings.ENABLED:
        logging.getLogger(__name__).info("UPnP router mapping worker disabled by DRouterMappings.ENABLED.")
        return
    stopping = Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    MaintainRouterMappings(RouterMappings()).run(stopping)


if __name__ == "__main__":
    main()
