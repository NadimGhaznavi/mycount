"""Compose the collector and run it under Gunicorn."""

import logging

from gunicorn.app.base import BaseApplication

from mycount.activity.BrowserMetadata import BrowserMetadata
from mycount.activity.CollectVisit import CollectVisit
from mycount.constants.DMyCount import DMyCount
from mycount.constants.DSecurityEvents import DSecurityEvents
from mycount.interface.Network import Network
from mycount.interface.CollectorHttp import CollectorHttp
from mycount.interface.ServiceLogger import ServiceLogger
from mycount.interface.SecurityEvents import SecurityEvents
from mycount.interface.VisitPayload import VisitPayload


class MyCountServer(BaseApplication):
    def load_config(self) -> None:
        interface, port = Network.binding("backend")
        self.cfg.set("bind", f"{interface}:{port}")
        self.cfg.set("workers", DMyCount.WORKERS)
        self.cfg.set("timeout", DMyCount.REQUEST_TIMEOUT)
        self.cfg.set("graceful_timeout", DMyCount.REQUEST_TIMEOUT)
        self.cfg.set("accesslog", None)
        self.cfg.set("errorlog", "-")
        self.cfg.set("forwarded_allow_ips", "")
        self.cfg.set("logger_class", ServiceLogger)

    def load(self) -> CollectorHttp:
        logger = logging.getLogger(DSecurityEvents.LOGGER)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.handlers = [handler]
        logger.setLevel(logging.WARNING)
        logger.propagate = False
        security_events = SecurityEvents(logger, DSecurityEvents.EVENTS)
        collector = CollectVisit(
            VisitPayload(), BrowserMetadata(),
        )
        return CollectorHttp(collector, DMyCount.ORIGINS, security_events)
