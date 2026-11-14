"""Own IsoForest's schema, raw source snapshot, run history, and atomic publication."""

from datetime import datetime
import json

from mycount.constants.DIsoForest import DIsoForest
from mycount.constants.DClientDetails import DClientDetails
from mycount.entity.IsoForestResult import IsoForestResult
from mycount.entity.IsoForestVisit import IsoForestVisit
from mycount.interface.DbMgr import DbMgr


class IsoForestDb:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def apply_schema(self) -> None:
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS isoforest_runs (
                run_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                started_at DATETIME(6) NOT NULL,
                completed_at DATETIME(6) NULL,
                status VARCHAR(16) NOT NULL,
                feature_version VARCHAR(64) NOT NULL,
                ipv4_prefix TINYINT UNSIGNED NOT NULL,
                ipv6_prefix TINYINT UNSIGNED NOT NULL,
                window_hours SMALLINT UNSIGNED NOT NULL,
                source_views BIGINT UNSIGNED NOT NULL DEFAULT 0,
                source_max_view_id BIGINT UNSIGNED NULL,
                source_first_at DATETIME(6) NULL,
                source_last_at DATETIME(6) NULL,
                observation_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
                anomaly_observations BIGINT UNSIGNED NOT NULL DEFAULT 0,
                anomaly_views BIGINT UNSIGNED NOT NULL DEFAULT 0,
                elapsed_seconds DOUBLE NULL,
                manifest JSON NULL,
                model LONGBLOB NULL,
                error VARCHAR(255) NULL,
                CONSTRAINT ck_isoforest_run_status CHECK (status IN ('running', 'complete', 'failed')),
                INDEX idx_isoforest_complete (status, run_id)
            ) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        features = ", ".join(f"{name} DOUBLE " +
                             ("NULL" if name in DIsoForest.BROWSER_FEATURES else "NOT NULL")
                             for name in DIsoForest.FEATURES)
        self._db.execute(f"""
            CREATE TABLE IF NOT EXISTS isoforest_observations (
                run_id BIGINT UNSIGNED NOT NULL,
                observation_id BIGINT UNSIGNED NOT NULL,
                window_start DATETIME(6) NOT NULL,
                network_block VARCHAR(64) NOT NULL,
                site VARCHAR(100) NOT NULL,
                page_views BIGINT UNSIGNED NOT NULL,
                distinct_ips BIGINT UNSIGNED NOT NULL,
                {features},
                decision_score DOUBLE NOT NULL,
                is_anomaly BOOLEAN NOT NULL,
                PRIMARY KEY (run_id, observation_id),
                INDEX idx_isoforest_anomalies (run_id, is_anomaly, decision_score),
                CONSTRAINT fk_isoforest_observation_run FOREIGN KEY (run_id)
                    REFERENCES isoforest_runs(run_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)
        # Explicit, idempotent upgrade: older runs have no browser-context evidence.
        additions = ", ".join(f"ADD COLUMN IF NOT EXISTS {name} DOUBLE NULL"
                              for name in DIsoForest.BROWSER_FEATURES)
        self._db.execute(f"ALTER TABLE isoforest_observations {additions}")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS isoforest_observation_visits (
                run_id BIGINT UNSIGNED NOT NULL,
                page_view_id BIGINT UNSIGNED NOT NULL,
                observation_id BIGINT UNSIGNED NOT NULL,
                PRIMARY KEY (run_id, page_view_id),
                INDEX idx_isoforest_members (run_id, observation_id),
                CONSTRAINT fk_isoforest_member_observation FOREIGN KEY (run_id, observation_id)
                    REFERENCES isoforest_observations(run_id, observation_id) ON DELETE CASCADE,
                CONSTRAINT fk_isoforest_member_view FOREIGN KEY (page_view_id)
                    REFERENCES page_views(page_view_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """)

    def raw_visits(self) -> list[IsoForestVisit]:
        """Read every collected visit, including Basic Bots and explicit test traffic."""
        details = [(key, column) for key, column, _ in DClientDetails.COLUMNS
                   if key in DIsoForest.PROFILE_FIELDS or key in DIsoForest.TEMPLATE_FIELDS]
        rows = self._db.query(f"""
            SELECT v.page_view_id, v.received_at, p.site, p.url, v.ip_address, v.user_agent,
                   v.timezone AS geoip_timezone, v.os_family, v.referrer_host,
                   (SELECT language_tag FROM page_view_languages l
                    WHERE l.page_view_id = v.page_view_id AND l.preference_order = 1) AS primary_language,
                   {', '.join('v.' + column for _, column in details)}
            FROM page_views v JOIN pages p ON p.page_id = v.page_id
            ORDER BY v.received_at, v.page_view_id
        """)
        visits = []
        for row in rows:
            client = tuple((key, row.pop(column)) for key, column in details)
            visits.append(IsoForestVisit(**row, client_details=client))
        return visits

    def start_run(self, started_at: datetime) -> int:
        return self._db.insert("""
            INSERT INTO isoforest_runs
                (started_at, status, feature_version, ipv4_prefix, ipv6_prefix, window_hours)
            VALUES (%s, 'running', %s, %s, %s, %s)
        """, (started_at, DIsoForest.FEATURE_VERSION, DIsoForest.IPV4_PREFIX,
              DIsoForest.IPV6_PREFIX, DIsoForest.WINDOW_HOURS))

    def fail_interrupted_runs(self, completed_at: datetime) -> None:
        """The caller holds the installation's worker lock, so no prior worker remains."""
        self._db.execute("""
            UPDATE isoforest_runs SET status = 'failed', completed_at = %s,
                error = 'Previous worker exited before completing.' WHERE status = 'running'
        """, (completed_at,))

    def fail_run(self, run_id: int, completed_at: datetime, error: str) -> None:
        # A lost commit acknowledgement must not demote an already published run.
        self._db.execute("""
            UPDATE isoforest_runs SET status = 'failed', completed_at = %s, error = %s
            WHERE run_id = %s AND status = 'running'
        """, (completed_at, error, run_id))

    def publish(self, run_id: int, visits: list[IsoForestVisit], result: IsoForestResult,
                completed_at: datetime, elapsed_seconds: float) -> None:
        observations = []
        members = []
        anomaly_views = anomaly_observations = 0
        for index, (observation, decision) in enumerate(zip(result.observations, result.decisions), start=1):
            anomaly = decision < 0
            count = len(observation.page_view_ids)
            anomaly_observations += anomaly
            anomaly_views += count if anomaly else 0
            observations.append((run_id, index, observation.window_start, observation.network_block,
                                 observation.site, count, observation.distinct_ips,
                                 *observation.features, decision, anomaly))
            members.extend((run_id, view_id, index) for view_id in observation.page_view_ids)
        columns = ("run_id", "observation_id", "window_start", "network_block", "site", "page_views",
                   "distinct_ips", *DIsoForest.FEATURES, "decision_score", "is_anomaly")
        with self._db.transaction():
            if observations:
                self._db.execute_many(f"""
                    INSERT INTO isoforest_observations ({', '.join(columns)})
                    VALUES ({', '.join('%s' for _ in columns)})
                """, observations)
                self._db.execute_many("""
                    INSERT INTO isoforest_observation_visits (run_id, page_view_id, observation_id)
                    VALUES (%s, %s, %s)
                """, members)
            self._db.execute("""
                UPDATE isoforest_runs SET completed_at = %s, status = 'complete',
                    source_views = %s, source_max_view_id = %s, source_first_at = %s, source_last_at = %s,
                    observation_count = %s, anomaly_observations = %s, anomaly_views = %s,
                    elapsed_seconds = %s, manifest = %s, model = %s
                WHERE run_id = %s AND status = 'running'
            """, (completed_at, len(visits), max((visit.page_view_id for visit in visits), default=None),
                  min((visit.received_at for visit in visits), default=None),
                  max((visit.received_at for visit in visits), default=None),
                  len(observations), anomaly_observations, anomaly_views, elapsed_seconds,
                  json.dumps(result.manifest), result.model, run_id))

    def active_run(self) -> dict[str, object] | None:
        rows = self._runs("WHERE status = 'complete' ORDER BY run_id DESC LIMIT 1")
        return rows[0] if rows else None

    def recent_runs(self) -> list[dict[str, object]]:
        return self._runs("ORDER BY run_id DESC LIMIT %s", (DIsoForest.HISTORY_LIMIT,))

    def run(self, run_id: int) -> dict[str, object] | None:
        rows = self._runs("WHERE run_id = %s", (run_id,))
        return rows[0] if rows else None

    def _runs(self, suffix: str, parameters: tuple = ()) -> list[dict[str, object]]:
        rows = self._db.query(f"""
            SELECT run_id, started_at, completed_at, status, feature_version,
                   ipv4_prefix, ipv6_prefix, window_hours, source_views, source_max_view_id,
                   source_first_at, source_last_at, observation_count,
                   anomaly_observations, anomaly_views, elapsed_seconds, manifest, error
            FROM isoforest_runs {suffix}
        """, parameters)
        for row in rows:
            if row["manifest"] is not None:
                row["manifest"] = json.loads(row["manifest"])
        return rows

    def observations(self, run_id: int) -> list[dict[str, object]]:
        return self._db.query("""
            SELECT * FROM isoforest_observations WHERE run_id = %s
            ORDER BY is_anomaly DESC, decision_score, observation_id LIMIT %s
        """, (run_id, DIsoForest.OBSERVATION_LIMIT))
