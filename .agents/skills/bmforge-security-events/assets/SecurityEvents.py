"""Emit request-scoped security events through the application's journal logger.

Only the trusted ingress adapter binds an address; business logic calls emit().
This component has no Fail2ban, ZMQ, firewall, retry or storage dependency.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from ipaddress import ip_address
import logging
import re


BMFORGE_COMPONENT = {"id": "bmforge.security-events", "spec_version": "0.1.0"}

_SOURCE_ADDRESS: ContextVar[str | None] = ContextVar(
    "bmforge.security-events.source", default=None
)
_EVENT_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")


class SecurityEvents:
    """Small fire-and-forget publisher; the host systemd unit owns journald output."""

    def __init__(self, logger: logging.Logger, event_names: tuple[str, ...]):
        if not event_names or any(
            not isinstance(name, str) or _EVENT_NAME.fullmatch(name) is None
            for name in event_names
        ):
            raise ValueError("Security event names must be approved ASCII tokens")
        self._logger = logger
        self._names = frozenset(event_names)

    @contextmanager
    def trusted_source(self, address: str):
        """Bind only the already-verified peer/proxy source at the ingress boundary."""
        try:
            if not isinstance(address, str) or "%" in address:
                raise ValueError("Client source must be a numeric IP address")
            parsed = ip_address(address)
            if parsed.is_unspecified or parsed.is_multicast:
                raise ValueError("Unusable client source address")
            normalized = str(parsed)
        except ValueError as error:
            raise ValueError("Client source must be a numeric IP address") from error
        token = _SOURCE_ADDRESS.set(normalized)
        try:
            yield
        finally:
            _SOURCE_ADDRESS.reset(token)

    def emit(self, event: str) -> None:
        """Publish one event, without a ban request, acknowledgement or retry."""
        if event not in self._names:
            raise ValueError("Unknown security event name")
        address = _SOURCE_ADDRESS.get()
        if address is None:
            raise RuntimeError("No trusted client source bound to this request")
        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        self._logger.warning("%s SECURITY event=%s ip=%s", timestamp, event, address)
