"""Validate browser input once and convert it to application data."""

from datetime import datetime, timezone
import re
from urllib.parse import urlsplit
from uuid import UUID

from mycount.entity.Visit import Visit
from mycount.constants.DMyCount import DMyCount
from mycount.interface.VisitorDetails import VisitorDetails


class InvalidVisit(ValueError):
    """The external payload does not satisfy the collection contract."""


class VisitPayload:
    def resolve(self, payload: object, origin: str) -> tuple[Visit, str]:
        """Return validated visit data and its user-agent string for enrichment."""
        if (not isinstance(payload, dict) or not DMyCount.PAYLOAD_FIELDS <= payload.keys()
                or payload.keys() - DMyCount.PAYLOAD_FIELDS - DMyCount.OPTIONAL_PAYLOAD_FIELDS):
            raise InvalidVisit("Invalid payload fields.")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != DMyCount.SCHEMA_VERSION:
            raise InvalidVisit("Unsupported schema_version.")
        site = payload["site"]
        if (payload["event"] != DMyCount.EVENT or not isinstance(site, str)
                or not 1 <= len(site) <= DMyCount.MAX_SITE_LENGTH
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", site) is None):
            raise InvalidVisit("Invalid event or site.")

        url = payload["url"]
        if not isinstance(url, str) or not url or any(ord(c) < 33 or ord(c) == 127 or c == "\\" for c in url):
            raise InvalidVisit("Invalid page URL.")
        try:
            url.encode("utf-8")
            address = urlsplit(url)
            allowed_address = urlsplit(origin)
            same_origin = (
                address.scheme == allowed_address.scheme
                and address.hostname == allowed_address.hostname
                and (address.port or DMyCount.HTTPS_PORT) == (allowed_address.port or DMyCount.HTTPS_PORT)
            )
        except (ValueError, UnicodeError) as error:
            raise InvalidVisit("Invalid page URL.") from error
        if not same_origin or address.username is not None or address.password is not None:
            raise InvalidVisit("Page URL must belong to the configured site.")

        languages = payload["languages"]
        if not isinstance(languages, list) or len(languages) > DMyCount.MAX_LANGUAGES:
            raise InvalidVisit("Invalid languages.")
        for language in languages:
            if (not isinstance(language, str) or len(language) > DMyCount.MAX_LANGUAGE_LENGTH
                    or re.fullmatch(DMyCount.LANGUAGE_PATTERN, language) is None):
                raise InvalidVisit("Invalid language tag.")
        agent = payload["user_agent"]
        if not isinstance(agent, str) or len(agent) > DMyCount.MAX_USER_AGENT_LENGTH:
            raise InvalidVisit("Invalid user_agent.")
        try:
            agent.encode("utf-8")
        except UnicodeError as error:
            raise InvalidVisit("Invalid user_agent.") from error

        try:
            referrer_host = VisitorDetails.referrer_host(payload.get("referrer"))
            client_details = VisitorDetails.resolve(payload.get("client_details", {}))
        except ValueError as error:
            raise InvalidVisit(str(error)) from error

        search = payload.get("search")
        if search is not None:
            if (not isinstance(search, str) or (search and not search.startswith("?"))
                    or "#" in search or any(ord(c) < 32 or ord(c) == 127 for c in search)):
                raise InvalidVisit("Invalid search.")
            try:
                search.encode("utf-8")
            except UnicodeError as error:
                raise InvalidVisit("Invalid search.") from error

        visitor_id = payload.get("visitor_id")
        if visitor_id is not None:
            if (not isinstance(visitor_id, str)
                    or re.fullmatch(DMyCount.VISITOR_ID_PATTERN, visitor_id) is None):
                raise InvalidVisit("Invalid visitor_id; expected a lowercase UUIDv4.")
            visitor_id = UUID(visitor_id).bytes

        visit = Visit(
            site=site,
            url=origin + (address.path or "/"),
            received_at=datetime.now(timezone.utc),
            languages=tuple(languages),
            referrer_host=referrer_host,
            referrer=payload.get("referrer") or None,
            search=search,
            user_agent=agent or None,
            client_details=client_details,
            visitor_id=visitor_id,
        )
        return visit, agent
