"""Handle HTTP requests for the control pages."""

from http.server import BaseHTTPRequestHandler
import logging
import json
import sqlite3
from urllib.parse import parse_qs, urlsplit

import pymysql
from werkzeug.exceptions import RequestEntityTooLarge

from mycount.activity.SaveMarketingPost import SaveMarketingPost
from mycount.constants.DMyCount import DMyCount
from mycount.constants.DMarketing import DMarketing
from mycount.interface.DbMgr import DbMgr
from mycount.interface.MarketingDb import MarketingDb
from mycount.interface.MarketingForm import MarketingForm
from mycount.interface.MarketingScreenshots import MarketingScreenshots
from mycount.interface.MarketingUpload import MarketingUpload
from mycount.activity.ReadReports import ReadReports
from mycount.entity.Report import Report
from mycount.entity.ReportOptions import ReportOptions
from mycount.interface.ReportQuery import ReportQuery
from mycount.interface.DbCommitUncertain import DbCommitUncertain
from mycount.server.ControlPages import ControlPages
from mycount.interface.CityLocations import CityLocations
from mycount.interface.CitySchedule import CitySchedule


class ControlHandler(BaseHTTPRequestHandler):
    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(DMyCount.REQUEST_TIMEOUT)

    def do_GET(self) -> None:
        request = urlsplit(self.path)
        path = request.path
        if path == "/api/city-schedule":
            self.city_schedule()
        elif path in ("/", "/marketing", "/map"):
            query = parse_qs(request.query, keep_blank_values=True)
            try:
                options = ReportQuery.resolve(query)
            except ValueError as error:
                self.send_error(400, str(error))
                return
            if path == "/marketing":
                self.marketing(options, saved=query.get("saved") == ["1"])
                return
            if path == "/map":
                self.visitor_map(options)
                return
            try:
                report = ReadReports().metrics(options)
            except pymysql.MySQLError:
                logging.exception("Unable to read site visits")
                self.respond(503, ControlPages().render(Report(options, [], None), error="Site visits unavailable."),
                             "text/html; charset=utf-8")
                return
            self.respond(200, ControlPages().render(report), "text/html; charset=utf-8")
        elif path == "/reference":
            first_visit_at = None
            try:
                first_visit_at = ReadReports().first_visit_at()
            except pymysql.MySQLError:
                logging.exception("Unable to read first visit for reference header")
            self.respond(200, ControlPages().reference(first_visit_at), "text/html; charset=utf-8")
        elif path.startswith("/pages/marketing/"):
            try:
                image = MarketingScreenshots().read(path.lstrip("/"))
            except FileNotFoundError:
                self.send_error(404, "Screenshot not found")
                return
            except OSError:
                logging.exception("Unable to read marketing screenshot")
                self.send_error(503, "Screenshot unavailable")
                return
            self.respond(200, image, "image/png")
        elif path == "/health":
            self.respond(200, b'{"status":"ok","service":"mycount-control"}', "application/json")
        else:
            self.send_error(404, "Page not found")

    def visitor_map(self, options: ReportOptions) -> None:
        try:
            report = ReadReports().visitor_map(options)
        except pymysql.MySQLError:
            logging.exception("Unable to read visitor locations")
            self.respond(503, ControlPages().visitor_map(Report(options, [], None),
                         error="Visitor locations unavailable."), "text/html; charset=utf-8")
            return
        self.respond(200, ControlPages().visitor_map(report), "text/html; charset=utf-8")

    def marketing(self, options: ReportOptions, *, saved: bool = False) -> None:
        try:
            report = ReadReports().marketing(options)
        except pymysql.MySQLError:
            logging.exception("Unable to read marketing events")
            self.respond(503, ControlPages().marketing(Report(options, [], None), error="Marketing data unavailable."),
                         "text/html; charset=utf-8")
            return
        self.respond(200, ControlPages().marketing(report, saved=saved), "text/html; charset=utf-8")

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in ("/marketing", "/api/city-schedule"):
            self.send_error(404, "Page not found")
            return
        origin = self.headers.get("Origin")
        try:
            parsed_origin = urlsplit(origin) if origin else None
        except ValueError:
            self.send_error(403, "Invalid submission origin")
            return
        if parsed_origin and (parsed_origin.scheme not in ("http", "https")
                              or parsed_origin.netloc != self.headers.get("Host")):
            self.send_error(403, "Cross-site submission refused")
            return
        if path == "/api/city-schedule":
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                self.send_error(403, "Cross-site submission refused")
                return
            self.city_schedule(update=True)
            return
        content_type = self.headers.get("Content-Type", "")
        if content_type.split(";", 1)[0] not in ("application/x-www-form-urlencoded", "multipart/form-data"):
            self.send_error(415, "Expected form data")
            return
        fields = {}
        try:
            if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
                self.send_error(400, "Supply one Content-Length and no Transfer-Encoding")
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= DMarketing.MAX_SCREENSHOT_BYTES + DMarketing.MAX_FORM_BYTES:
                self.send_error(413, "Invalid form size")
                return
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Incomplete marketing form.")
            fields, screenshot = MarketingUpload.parse(body, content_type)
            post = MarketingForm.parse(fields)
            if screenshot is not None:
                MarketingScreenshots.validate(screenshot)
        except RequestEntityTooLarge:
            self.send_error(413, "Screenshot or form is too large")
            return
        except (ValueError, UnicodeError) as error:
            self.respond(400, ControlPages().marketing(Report(ReportQuery.resolve({}), [], None), error=str(error), fields=fields),
                         "text/html; charset=utf-8")
            return
        try:
            db = DbMgr()
            try:
                SaveMarketingPost(MarketingDb(db), MarketingScreenshots()).save(post, screenshot)
            finally:
                db.close()
        except DbCommitUncertain:
            logging.exception("Marketing save outcome uncertain")
            self.respond(503, ControlPages().marketing(Report(ReportQuery.resolve({}), [], None),
                         error="Save could not be confirmed. Retry this form to confirm the same posting.", fields=fields),
                         "text/html; charset=utf-8")
            return
        except (pymysql.MySQLError, OSError):
            logging.exception("Unable to save marketing event")
            self.respond(503, ControlPages().marketing(Report(ReportQuery.resolve({}), [], None), error="Posting could not be saved. Please retry.", fields=fields),
                         "text/html; charset=utf-8")
            return
        self.respond(303, b"", "text/html; charset=utf-8", location="/marketing?saved=1")

    def city_schedule(self, *, update: bool = False) -> None:
        def respond(status, payload):
            self.respond(status, json.dumps(payload).encode(), "application/json; charset=utf-8")

        if update:
            if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                respond(415, {"error": "Expected JSON schedule settings."})
                return
            try:
                if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
                    raise ValueError("Supply one Content-Length and no Transfer-Encoding.")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= DMyCount.MAX_BODY_BYTES:
                    raise ValueError("Invalid schedule request size.")
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError("Incomplete schedule request.")
                values = json.loads(body)
                if not isinstance(values, dict) or values.keys() != {"enabled", "expression"}:
                    raise ValueError("Provide an enabled flag and a five-field cron expression.")
                values = CitySchedule.validate(**values)
            except (ValueError, UnicodeError) as error:
                respond(400, {"error": str(error)})
                return
        try:
            schedule = CitySchedule()
            values = schedule.update(**values) if update else schedule.read()
            dataset = CityLocations().status()
        except (OSError, ValueError, sqlite3.Error):
            logging.exception("Unable to access city refresh settings")
            respond(503, {"error": "City refresh settings unavailable. Reload to check the saved schedule before retrying."})
            return
        respond(200, {"schedule": values, "dataset": dataset})

    def respond(self, status: int, body: bytes, content_type: str, *, location: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if location is not None:
            self.send_header("Location", location)
        self.end_headers()
        self.wfile.write(body)
