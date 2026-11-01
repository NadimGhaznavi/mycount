"""Stable event identifiers consumed by the host's security-event jails."""

from typing import Final


class DSecurityEvents:
    LOGGER: Final[str] = "mycount.security"
    COLLECTION_REQUEST: Final[str] = "collection_request"
    MALFORMED_PAYLOAD: Final[str] = "malformed_payload"
    EVENTS: Final[tuple[str, ...]] = (COLLECTION_REQUEST, MALFORMED_PAYLOAD)
