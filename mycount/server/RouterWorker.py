"""Run router maintenance independently of the HTTP workers."""

import logging
import signal
from threading import Event

from mycount.activity.MaintainRouterMappings import MaintainRouterMappings
from mycount.interface.RouterMappings import RouterMappings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stopping = Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    signal.signal(signal.SIGINT, lambda *_: stopping.set())
    MaintainRouterMappings(RouterMappings()).run(stopping)


if __name__ == "__main__":
    main()
