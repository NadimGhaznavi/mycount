"""Resolve the visitor address supplied by the local Caddy proxy."""

from ipaddress import ip_address

from werkzeug.wrappers import Request

from mycount.constants.DCaddy import DCaddy
from mycount.constants.DMyCount import DMyCount
from mycount.interface.VisitPayload import InvalidVisit


class VisitorAddress:
    @staticmethod
    def resolve(request: Request) -> str | None:
        address = request.remote_addr
        if address == DMyCount.HOST:
            forwarded = request.headers.get(DCaddy.VISITOR_HEADER)
            if forwarded is not None:
                try:
                    return str(ip_address(forwarded))
                except ValueError as error:
                    raise InvalidVisit("Invalid proxy address.") from error
        return address
