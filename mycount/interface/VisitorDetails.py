"""Validate optional external browser details and reduce referrers to hosts."""

from ipaddress import ip_address
import math
import re
from urllib.parse import urlsplit

from mycount.constants.DVisitorDetails import DVisitorDetails


class VisitorDetails:
    @staticmethod
    def referrer_host(value: object) -> str | None:
        if value is None or value == "":
            return None
        if (not isinstance(value, str) or len(value) > DVisitorDetails.MAX_REFERRER_LENGTH
                or any(ord(c) < 33 or ord(c) == 127 or c == "\\" for c in value)):
            raise ValueError("Invalid referrer.")
        try:
            value.encode("utf-8")
            parsed = urlsplit(value)
            host = parsed.hostname
            port = parsed.port
            if (parsed.scheme not in ("http", "https") or not host
                    or parsed.username is not None or parsed.password is not None or port == 0):
                raise ValueError("Invalid referrer.")
            host = host.encode("idna").decode("ascii").lower().rstrip(".")
            if len(host) > DVisitorDetails.MAX_HOST_LENGTH:
                raise ValueError("Invalid referrer host.")
            if ":" in host:
                ip_address(host)
            elif any(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None
                     for label in host.split(".")):
                raise ValueError("Invalid referrer host.")
            return host
        except (ValueError, UnicodeError) as error:
            raise ValueError("Invalid referrer.") from error

    @staticmethod
    def resolve(value: object) -> tuple[tuple[str, str | int | float | bool], ...]:
        if not isinstance(value, dict):
            raise ValueError("Invalid client_details.")
        allowed = (DVisitorDetails.INTEGER_RANGES.keys() | DVisitorDetails.NUMBER_RANGES.keys()
                   | DVisitorDetails.BOOLEAN_FIELDS | DVisitorDetails.TEXT_FIELDS
                   | DVisitorDetails.ENUM_FIELDS.keys())
        if value.keys() - allowed:
            raise ValueError("Unknown client_details field.")
        result = []
        for name, item in value.items():
            # Unsupported browser APIs are sent as null or omitted, never as zero/false.
            if item is None:
                continue
            if name in DVisitorDetails.INTEGER_RANGES:
                low, high = DVisitorDetails.INTEGER_RANGES[name]
                valid = type(item) is int and low <= item <= high
            elif name in DVisitorDetails.NUMBER_RANGES:
                low, high = DVisitorDetails.NUMBER_RANGES[name]
                valid = type(item) in (int, float) and low <= item <= high and math.isfinite(item)
            elif name in DVisitorDetails.BOOLEAN_FIELDS:
                valid = type(item) is bool
            elif name in DVisitorDetails.ENUM_FIELDS:
                valid = isinstance(item, str) and item in DVisitorDetails.ENUM_FIELDS[name]
            else:
                valid = (isinstance(item, str) and len(item) <= DVisitorDetails.TEXT_LENGTH
                         and not any(ord(c) < 32 or ord(c) == 127 for c in item))
                if valid:
                    try:
                        item.encode("utf-8")
                    except UnicodeError:
                        valid = False
            if not valid:
                raise ValueError(f"Invalid client_details.{name}.")
            result.append((name, item))
        return tuple(result)
