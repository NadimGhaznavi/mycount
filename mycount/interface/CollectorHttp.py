"""HTTP and CORS boundary for the visitor collector."""

import logging

import pymysql
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Request, Response

from mycount.activity.CollectVisit import CollectVisit
from mycount.constants.DMyCount import DMyCount
from mycount.interface.VisitPayload import InvalidVisit
from mycount.interface.VisitorAddress import VisitorAddress


class CollectorHttp:
    def __init__(self, collector: CollectVisit, origin: str) -> None:
        self._collector = collector
        self._origin = origin

    def __call__(self, environ, start_response):
        request = Request(environ)
        request.max_content_length = DMyCount.MAX_BODY_BYTES
        try:
            response = self._respond(request)
        except HTTPException as error:
            response = Response(status=error.code)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = "Origin"
        if request.headers.get("Origin") == self._origin:
            response.headers["Access-Control-Allow-Origin"] = self._origin
        return response(environ, start_response)

    def _respond(self, request: Request) -> Response:
        if request.path == DMyCount.HEALTH_PATH and request.method in ("GET", "HEAD"):
            return Response(status=204)
        if request.path != DMyCount.COLLECTION_PATH:
            return Response(status=404)
        if request.headers.get("Origin") != self._origin:
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
            self._collector.record(payload, VisitorAddress.resolve(request))
        except InvalidVisit:
            return Response(status=400)
        except pymysql.OperationalError as error:
            logging.getLogger(__name__).error("Database unavailable (code %s).", error.args[0])
            return Response(status=503)
        return Response(status=204)
