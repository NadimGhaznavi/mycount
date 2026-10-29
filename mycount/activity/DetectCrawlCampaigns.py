"""Recognize sustained page sweeps behind rotating browser identities."""

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import logging
from urllib.parse import urlsplit

from mycount.constants.DCrawlCampaigns import DCrawlCampaigns
from mycount.entity.CampaignVisit import CampaignVisit
from mycount.entity.Visit import Visit
from mycount.interface.VisitDb import VisitDb


class DetectCrawlCampaigns:
    def __init__(self, visits: VisitDb) -> None:
        self._visits = visits

    @staticmethod
    def is_candidate(visit: Visit) -> bool:
        details = dict(visit.client_details)
        return (visit.browser_family == DCrawlCampaigns.BROWSER and visit.os_family == DCrawlCampaigns.OS
                and details.get("platform") == DCrawlCampaigns.PLATFORM
                and details.get("vendor") == DCrawlCampaigns.VENDOR)

    def classify(self, site: str, end: datetime) -> int:
        """Revisit the evidence on arrival; retain earlier campaign classifications."""
        end = end.astimezone(timezone.utc).replace(tzinfo=None)
        ids = self.find(self._visits.campaign_candidates(
            site, start=end - timedelta(hours=DCrawlCampaigns.WINDOW_HOURS), end=end))
        changed = self._visits.mark_campaign_bots(ids)
        if changed:
            logging.getLogger("gunicorn.error").info(
                "Classified %d crawl campaign page views on site %s", changed, site)
        return changed

    @classmethod
    def find(cls, visits: list[CampaignVisit]) -> tuple[int, ...]:
        """Require independent identities, a page sweep, short pairs, and cadence.

        Each origin and site is assessed independently. A browser version, country,
        IP range, or hardware fingerprint never establishes a campaign.
        """
        identities = defaultdict(list)
        for visit in visits:
            address = urlsplit(visit.url)
            identities[(visit.site, address.scheme, address.netloc, visit.visitor_id)].append(visit)
        cohorts = defaultdict(list)
        for (site, scheme, host, _), rows in identities.items():
            rows.sort(key=lambda row: (row.received_at, row.page_view_id))
            if len(rows) > 2 or len({row.ip_address for row in rows}) != 1:
                continue
            if any(row.referrer_host not in (None, urlsplit(row.url).hostname) for row in rows):
                continue
            paths = [urlsplit(row.url).path for row in rows]
            if len(rows) == 2:
                seconds = (rows[1].received_at - rows[0].received_at).total_seconds()
                if (paths[0] != "/" or paths[1] == "/"
                        or not DCrawlCampaigns.MIN_PAIR_SECONDS <= seconds <= DCrawlCampaigns.MAX_PAIR_SECONDS):
                    continue
            cohorts[(site, scheme, host)].append(rows)
        excluded = set()
        for sessions in cohorts.values():
            sessions.sort(key=lambda rows: (rows[0].received_at, rows[0].page_view_id))
            window = deque()
            for session in sessions:
                window.append(session)
                cutoff = session[0].received_at - timedelta(hours=DCrawlCampaigns.WINDOW_HOURS)
                while window[0][0].received_at < cutoff:
                    window.popleft()
                if cls._matches(list(window)):
                    excluded.update(row.page_view_id for rows in window for row in rows)
        return tuple(sorted(excluded))

    @classmethod
    def _matches(cls, sessions: list[list[CampaignVisit]]) -> bool:
        if len(sessions) < DCrawlCampaigns.MIN_IDENTITIES:
            return False
        if len({rows[0].ip_address for rows in sessions}) != len(sessions):
            return False
        pages = [row.url for rows in sessions for row in rows if urlsplit(row.url).path != "/"]
        if len(pages) < DCrawlCampaigns.MIN_PAGES or len(set(pages)) != len(pages):
            return False
        if sum(len(rows) == 2 for rows in sessions) < DCrawlCampaigns.MIN_PAIRS:
            return False
        times = [rows[0].received_at for rows in sessions]
        regular = set()
        for start in range(len(times) - DCrawlCampaigns.CADENCE_SESSIONS + 1):
            run = times[start:start + DCrawlCampaigns.CADENCE_SESSIONS]
            gaps = [(right - left).total_seconds() for left, right in zip(run, run[1:])]
            if cls._regular_gaps(gaps):
                regular.update(range(start, start + DCrawlCampaigns.CADENCE_SESSIONS))
        return len(regular) >= len(sessions) * DCrawlCampaigns.MIN_CADENCE_SHARE

    @staticmethod
    def _regular_gaps(gaps: list[float]) -> bool:
        for gap in gaps:
            for multiple in range(1, DCrawlCampaigns.MAX_INTERVAL_MULTIPLE + 1):
                period = gap / multiple
                if not DCrawlCampaigns.MIN_INTERVAL_SECONDS <= period <= DCrawlCampaigns.MAX_INTERVAL_SECONDS:
                    continue
                if all(1 <= round(value / period) <= DCrawlCampaigns.MAX_INTERVAL_MULTIPLE
                       and abs(value - round(value / period) * period)
                       <= period * DCrawlCampaigns.INTERVAL_TOLERANCE for value in gaps):
                    return True
        return False


def main() -> None:
    """Preview a historical scan; --apply explicitly persists its classifications."""
    import argparse
    from mycount.interface.DbMgr import DbMgr

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    db = DbMgr()
    try:
        visits = VisitDb(db)
        with db.transaction(read_only=True):
            ids = DetectCrawlCampaigns.find(visits.campaign_candidates(args.site))
        print(f"Site {args.site}: {len(ids)} campaign page views detected.")
        if args.apply:
            print(f"Newly classified: {visits.mark_campaign_bots(ids)}.")
        else:
            print("Preview only; use --apply to persist classifications.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
