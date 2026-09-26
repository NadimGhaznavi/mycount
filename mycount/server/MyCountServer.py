"""Compose the collector and run it under Gunicorn."""

from gunicorn.app.base import BaseApplication

from mycount.activity.BrowserMetadata import BrowserMetadata
from mycount.activity.CollectVisit import CollectVisit
from mycount.constants.DMyCount import DMyCount
from mycount.interface.CollectorHttp import CollectorHttp
from mycount.interface.ServiceLogger import ServiceLogger
from mycount.interface.VisitPayload import VisitPayload


class MyCountServer(BaseApplication):
    def load_config(self) -> None:
        self.cfg.set("bind", f"{DMyCount.HOST}:{DMyCount.PORT}")
        self.cfg.set("workers", DMyCount.WORKERS)
        self.cfg.set("timeout", DMyCount.REQUEST_TIMEOUT)
        self.cfg.set("graceful_timeout", DMyCount.REQUEST_TIMEOUT)
        self.cfg.set("accesslog", None)
        self.cfg.set("errorlog", "-")
        self.cfg.set("forwarded_allow_ips", "")
        self.cfg.set("logger_class", ServiceLogger)

    def load(self) -> CollectorHttp:
        collector = CollectVisit(
            VisitPayload(DMyCount.SITE, DMyCount.ORIGIN), BrowserMetadata(),
        )
        return CollectorHttp(collector, DMyCount.ORIGIN)
