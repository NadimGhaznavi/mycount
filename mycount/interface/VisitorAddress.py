"""Resolve the visitor address supplied by the local Caddy proxy."""

from ipaddress import ip_address

from werkzeug.wrappers import Request

from mycount.constants.DCaddy import DCaddy
from mycount.interface.Network import Network
from mycount.interface.VisitPayload import InvalidVisit


class VisitorAddress:
    @staticmethod
    def resolve(request: Request) -> str:
        address = request.remote_addr
        if address == Network.destination("backend")[0]:
            address = request.headers.get(DCaddy.VISITOR_HEADER)
        try:
            if address is None or "%" in address:
                raise ValueError("Missing or scoped client address.")
            parsed = ip_address(address)
            if parsed.is_unspecified or parsed.is_multicast:
                raise ValueError("Unusable client address.")
            return str(parsed)
        except ValueError as error:
            raise InvalidVisit("Invalid client address.") from error
