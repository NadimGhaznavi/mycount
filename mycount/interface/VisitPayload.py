"""Validate browser input once and convert it to application data."""

from datetime import datetime, timezone
import re
from urllib.parse import urlsplit

from mycount.entity.Visit import Visit
from mycount.constants.DMyCount import DMyCount


class InvalidVisit(ValueError):
    """The external payload does not satisfy the collection contract."""


class VisitPayload:
    def __init__(self, site: str, origin: str) -> None:
        self._site = site
        self._origin = origin
        self._address = urlsplit(origin)

    def resolve(self, payload: object) -> tuple[Visit, str]:
        """Return validated visit data and a transient user-agent string."""
        if not isinstance(payload, dict) or payload.keys() != DMyCount.PAYLOAD_FIELDS:
            raise InvalidVisit("Invalid payload fields.")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != DMyCount.SCHEMA_VERSION:
            raise InvalidVisit("Unsupported schema_version.")
        if payload["event"] != DMyCount.EVENT or payload["site"] != self._site:
            raise InvalidVisit("Invalid event or site.")

        url = payload["url"]
        if not isinstance(url, str) or not url or any(ord(c) < 33 or ord(c) == 127 or c == "\\" for c in url):
            raise InvalidVisit("Invalid page URL.")
        try:
            url.encode("utf-8")
            address = urlsplit(url)
            same_origin = (
                address.scheme == self._address.scheme
                and address.hostname == self._address.hostname
                and (address.port or DMyCount.HTTPS_PORT) == (self._address.port or DMyCount.HTTPS_PORT)
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

        visit = Visit(
            site=self._site,
            url=self._origin + (address.path or "/"),
            received_at=datetime.now(timezone.utc),
            languages=tuple(languages),
        )
        return visit, agent
