"""Measure browser consistency and template reuse across unrelated networks."""

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address, ip_network
import json
import math
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mycount.constants.DIsoForest import DIsoForest
from mycount.entity.IsoForestVisit import IsoForestVisit


@dataclass(frozen=True)
class _TemplateMember:
    visit: IsoForestVisit
    network: str
    offset: float | None
    viewport: tuple[int, int] | None


class _TemplateWindow:
    """Count one latest browser observation per IP in a trailing time window."""

    def __init__(self) -> None:
        self._rows = deque()
        self._latest = {}
        self._counts = (Counter(), Counter(), Counter())

    def measure(self, member: _TemplateMember) -> dict[str, float]:
        cutoff = member.visit.received_at - timedelta(hours=DIsoForest.WINDOW_HOURS)
        while self._rows and self._rows[0].visit.received_at < cutoff:
            expired = self._rows.popleft()
            if self._latest.get(expired.visit.ip_address) is expired:
                self._remove(expired)
                del self._latest[expired.visit.ip_address]
        previous = self._latest.get(member.visit.ip_address)
        if previous is not None:
            self._remove(previous)
        self._rows.append(member)
        self._latest[member.visit.ip_address] = member
        for counter, value in zip(self._counts, (member.network, member.offset, member.viewport)):
            if value is not None:
                counter[value] += 1
        return dict(zip(
            ("template_ips_log", "template_networks_log", "template_timezones_log", "template_viewports_log"),
            (math.log1p(count) for count in (len(self._latest), *(len(c) for c in self._counts))),
        ))

    def _remove(self, member: _TemplateMember) -> None:
        for counter, value in zip(self._counts, (member.network, member.offset, member.viewport)):
            if value is not None:
                counter[value] -= 1
                if not counter[value]:
                    del counter[value]


class BuildIsoForestBrowserFeatures:
    def build(self, visits: list[IsoForestVisit]) -> dict[int, dict[str, float]]:
        features = {}
        templates = defaultdict(_TemplateWindow)
        for visit in sorted(visits, key=lambda value: (value.received_at, value.page_view_id)):
            details = dict(visit.client_details)
            browser_offset = self._offset(details.get("timezone"), visit.received_at)
            geoip_offset = self._offset(visit.geoip_timezone, visit.received_at)
            comparable = browser_offset is not None and geoip_offset is not None
            prefixes = DIsoForest.OS_PLATFORM_PREFIXES.get(visit.os_family)
            platform = details.get("platform")
            platform_known = prefixes is not None and bool(platform)
            values = dict.fromkeys(DIsoForest.BROWSER_FEATURES, 0.)
            values.update(
                timezone_coverage=float(comparable),
                timezone_mismatch_share=float(comparable and browser_offset != geoip_offset),
                timezone_gap_hours=abs(browser_offset - geoip_offset) if comparable else 0.,
                platform_os_coverage=float(platform_known),
                platform_os_mismatch_share=float(platform_known and not platform.startswith(prefixes)),
                direct_referrer_share=float(not visit.referrer_host),
            )
            # Incomplete historical records cannot establish a shared device template.
            if (visit.ip_address is not None and visit.user_agent and platform
                    and details.get("screen_width", 0) and details.get("screen_height", 0)):
                signature = json.dumps((visit.user_agent, visit.primary_language,
                    {name: details.get(name) for name in DIsoForest.TEMPLATE_FIELDS}), sort_keys=True)
                ipv4 = ip_address(visit.ip_address).version == 4
                network = str(ip_network(
                    f"{visit.ip_address}/{DIsoForest.IPV4_PREFIX if ipv4 else DIsoForest.IPV6_PREFIX}",
                    strict=False))
                width, height = details.get("viewport_width"), details.get("viewport_height")
                viewport = (width, height) if width and height else None
                member = _TemplateMember(visit, network, browser_offset, viewport)
                values.update(templates[visit.site, signature].measure(member))
                values["template_coverage"] = 1.
            features[visit.page_view_id] = values
        return features

    @staticmethod
    def _offset(name: str | None, stamp: datetime) -> float | None:
        """Treat absent or invalid external timezone names as unavailable evidence."""
        if not name:
            return None
        try:
            zone = ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            return None
        return stamp.replace(tzinfo=timezone.utc).astimezone(zone).utcoffset().total_seconds() / 3600
