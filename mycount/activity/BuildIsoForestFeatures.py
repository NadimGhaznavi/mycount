"""Aggregate all raw visits into the tested network-rotation representation."""

from collections import Counter, defaultdict
from datetime import datetime, timezone
from ipaddress import ip_address, ip_network
import json
import math
from statistics import median, pstdev
from urllib.parse import urlsplit

from mycount.constants.DIsoForest import DIsoForest
from mycount.entity.IsoForestObservation import IsoForestObservation
from mycount.entity.IsoForestVisit import IsoForestVisit


class BuildIsoForestFeatures:
    def build(self, visits: list[IsoForestVisit]) -> tuple[IsoForestObservation, ...]:
        seconds = DIsoForest.WINDOW_HOURS * 3600
        groups = defaultdict(list)
        networks = defaultdict(list)
        for visit in sorted(visits, key=lambda value: (value.received_at, value.page_view_id)):
            stamp = visit.received_at.replace(tzinfo=timezone.utc).timestamp()
            window = int(stamp // seconds) * seconds
            if visit.ip_address is None:
                # Missing addresses are unrelated observations, never a shared network.
                block = fine = medium = f"missing-ip:{visit.page_view_id}"
                address = block
            else:
                address = visit.ip_address
                ipv4 = ip_address(address).version == 4
                block = str(ip_network(f"{address}/{DIsoForest.IPV4_PREFIX if ipv4 else DIsoForest.IPV6_PREFIX}", strict=False))
                fine = str(ip_network(f"{address}/{24 if ipv4 else 64}", strict=False))
                medium = str(ip_network(f"{address}/{20 if ipv4 else 56}", strict=False))
            details = dict(visit.client_details)
            profile = json.dumps({name: details.get(name) for name in DIsoForest.PROFILE_FIELDS}, sort_keys=True)
            member = (visit, address, stamp, urlsplit(visit.url).path, profile, fine, medium)
            groups[window, block, visit.site].append(member)
            networks[window, block].append(member)
        network_ips = {key: self._representatives(members) for key, members in networks.items()}
        observations = []
        for (window, block, site), members in sorted(groups.items()):
            ips = self._representatives(members)
            network = network_ips[window, block]
            times = sorted(ip["time"] for ip in ips)
            gaps = [end - start for start, end in zip(times, times[1:])]
            gap_mean = sum(gaps) / len(gaps) if gaps else 0
            # Feature names retain the tested IPv4 definitions. For IPv6, the
            # corresponding fine/medium subnet sizes are /64 and /56.
            values = {
                "distinct_ips_log": math.log1p(len(ips)),
                "distinct_24_blocks_log": math.log1p(len({ip["fine"] for ip in ips})),
                "distinct_20_blocks_log": math.log1p(len({ip["medium"] for ip in ips})),
                "network_distinct_ips_log": math.log1p(len(network)),
                "network_distinct_24_blocks_log": math.log1p(len({ip["fine"] for ip in network})),
                "site_ip_share_of_network": len(ips) / len(network),
                "path_diversity_across_ips": len({ip["path"] for ip in ips}) / len(ips),
                "profile_diversity_across_ips": len({ip["profile"] for ip in ips}) / len(ips),
                "agent_diversity_across_ips": len({ip["agent"] for ip in ips}) / len(ips),
                "inter_ip_median_gap_log": math.log1p(median(gaps)) if gaps else 0.,
                "inter_ip_gap_cv": pstdev(gaps) / gap_mean if gap_mean > 0 else 0.,
            }
            observations.append(IsoForestObservation(
                datetime.fromtimestamp(window, timezone.utc).replace(tzinfo=None), block, site,
                tuple(member[0].page_view_id for member in members),
                len({member[0].ip_address for member in members} - {None}),
                tuple(values[name] for name in DIsoForest.FEATURES),
            ))
        return tuple(observations)

    @staticmethod
    def _representatives(members: list[tuple]) -> list[dict[str, object]]:
        by_ip = defaultdict(list)
        for member in members:
            by_ip[member[1]].append(member)
        return [{
            "time": median(member[2] for member in rows),
            "path": Counter(member[3] for member in rows).most_common(1)[0][0],
            "profile": Counter(member[4] for member in rows).most_common(1)[0][0],
            "agent": Counter(member[0].user_agent for member in rows).most_common(1)[0][0],
            "fine": rows[0][5], "medium": rows[0][6],
        } for rows in by_ip.values()]
