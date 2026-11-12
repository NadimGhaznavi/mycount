"""Run the independent, scheduled pipeline and publish only complete results."""

import argparse
from datetime import datetime, timezone
import logging
from time import perf_counter

from mycount.activity.BuildIsoForestFeatures import BuildIsoForestFeatures
from mycount.interface.IsoForestDb import IsoForestDb
from mycount.interface.IsoForestSchedule import IsoForestSchedule
from mycount.interface.DbMgr import DbMgr


class RunIsoForest:
    def __init__(self, schedule: IsoForestSchedule) -> None:
        self._schedule = schedule

    def run(self, *, scheduled: bool = False) -> int | None:
        with self._schedule.worker_lock() as locked:
            if not locked:
                return None
            requested = self._schedule.requested()
            if scheduled and not requested and not self._schedule.read()["enabled"]:
                return None
            db = DbMgr()
            try:
                store = IsoForestDb(db)
                started_at = datetime.now(timezone.utc).replace(tzinfo=None)
                store.fail_interrupted_runs(started_at)
                if scheduled and not requested:
                    recent = store.recent_runs()
                    if recent and not self._schedule.due(datetime.now().astimezone()):
                        return None
                    if recent and recent[0]["started_at"] >= started_at.replace(second=0, microsecond=0):
                        return None
                run_id = store.start_run(started_at)
                clock = perf_counter()
                try:
                    self._schedule.claim_request()
                    with db.transaction(read_only=True):
                        visits = store.raw_visits()
                    observations = BuildIsoForestFeatures().build(visits)
                    # Minute checks that are not due do not load the ML runtime.
                    from mycount.interface.IsoForestModel import IsoForestModel
                    result = IsoForestModel().fit(observations)
                    elapsed = perf_counter() - clock
                    store.publish(run_id, visits, result, datetime.now(timezone.utc).replace(tzinfo=None), elapsed)
                except Exception as error:
                    # Record failure, retain the last completed run, and propagate the cause.
                    try:
                        store.fail_run(run_id, datetime.now(timezone.utc).replace(tzinfo=None),
                                       f"{type(error).__name__}: run failed; see worker logs.")
                    except Exception as record_error:
                        error.add_note(f"Recording the failed run also failed: {type(record_error).__name__}.")
                        logging.exception("Unable to record failure of IsoForest run %s", run_id)
                    raise
                logging.info("IsoForest run %s complete: %s views, %s observations in %.3fs",
                             run_id, len(visits), len(observations), elapsed)
                return run_id
            finally:
                db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scheduled", action="store_true", help="Honor the web schedule and queued requests")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    RunIsoForest(IsoForestSchedule()).run(scheduled=args.scheduled)


if __name__ == "__main__":
    main()
