"""Handle HTTP requests for the control pages."""

from http.server import BaseHTTPRequestHandler
import logging
from urllib.parse import urlsplit

import pymysql

from mycount.constants.DMyCount import DMyCount
from mycount.interface.DbMgr import DbMgr
from mycount.interface.VisitDb import VisitDb
from mycount.server.ControlPages import ControlPages


class ControlHandler(BaseHTTPRequestHandler):
    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(DMyCount.REQUEST_TIMEOUT)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            try:
                db = DbMgr()
                try:
                    with db.transaction(read_only=True):
                        visits = VisitDb(db)
                        sites = visits.totals_by_site()
                        pages = visits.totals_by_page()
                finally:
                    db.close()
            except pymysql.MySQLError:
                logging.exception("Unable to read site visits")
                self.respond(503, ControlPages().render([], [], error="Site visits unavailable."),
                             "text/html; charset=utf-8")
                return
            self.respond(200, ControlPages().render(sites, pages), "text/html; charset=utf-8")
        elif path == "/health":
            self.respond(200, b'{"status":"ok","service":"mycount-control"}', "application/json")
        else:
            self.send_error(404, "Page not found")

    def respond(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)
