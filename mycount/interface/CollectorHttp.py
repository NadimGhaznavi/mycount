"""HTTP and CORS boundary for the visitor collector."""

import json
import logging
import re

import pymysql
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Request, Response

from mycount.activity.CollectVisit import CollectVisit
from mycount.activity.CountVisits import CountVisits
from mycount.constants.DMyCount import DMyCount
from mycount.interface.VisitPayload import InvalidVisit
from mycount.interface.VisitorAddress import VisitorAddress
from mycount.interface.GeoIpUnavailable import GeoIpUnavailable


class CollectorHttp:
    def __init__(self, collector: CollectVisit, origins: tuple[str, ...]) -> None:
        self._collector = collector
        self._origins = origins

    def __call__(self, environ, start_response):
        request = Request(environ)
        request.max_content_length = DMyCount.MAX_BODY_BYTES
        try:
            response = self._respond(request)
        except HTTPException as error:
            response = Response(status=error.code)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = "Origin"
        if request.headers.get("Origin") in self._origins:
            response.headers["Access-Control-Allow-Origin"] = request.headers["Origin"]
        return response(environ, start_response)

    def _respond(self, request: Request) -> Response:
        if request.path == DMyCount.HEALTH_PATH and request.method in ("GET", "HEAD"):
            return Response(status=204)
        if request.path == DMyCount.COUNT_PATH:
            return self._count(request)
        if request.path != DMyCount.COLLECTION_PATH:
            return Response(status=404)
        if request.headers.get("Origin") not in self._origins:
            return Response(status=403)
        if request.method == "OPTIONS":
            method = request.headers.get("Access-Control-Request-Method")
            headers = {value.strip().lower() for value in
                       request.headers.get("Access-Control-Request-Headers", "").split(",") if value.strip()}
            if method != "POST" or headers - {"content-type"}:
                return Response(status=403)
            return Response(status=204, headers={
                "Access-Control-Allow-Methods": "POST",
                "Access-Control-Allow-Headers": "Content-Type",
            })
        if request.method != "POST":
            return Response(status=405, headers={"Allow": "POST, OPTIONS"})
        payload = request.get_json()
        try:
            self._collector.record(payload, VisitorAddress.resolve(request), request.headers["Origin"])
        except InvalidVisit:
            return Response(status=400)
        except GeoIpUnavailable:
            logging.getLogger(__name__).exception("Geolocation unavailable.")
            return Response(status=503)
        except pymysql.OperationalError as error:
            logging.getLogger(__name__).error("Database unavailable (code %s).", error.args[0])
            return Response(status=503)
        return Response(status=204)

    def _count(self, request: Request) -> Response:
        if request.headers.get("Origin") not in self._origins:
            return Response(status=403)
        if request.method != "GET":
            return Response(status=405, headers={"Allow": "GET"})
        sites = request.args.getlist("site")
        if (len(sites) != 1 or not 1 <= len(sites[0]) <= DMyCount.MAX_SITE_LENGTH
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", sites[0]) is None):
            return Response(status=400)
        site = sites[0]
        try:
            visits = CountVisits().count(site)
        except pymysql.OperationalError as error:
            logging.getLogger(__name__).error("Counter database unavailable (code %s).", error.args[0])
            return Response(status=503)
        return Response(json.dumps({"site": site, "visits": visits}), mimetype="application/json")
