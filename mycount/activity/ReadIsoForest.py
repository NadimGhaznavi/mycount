"""Prepare the model-run history and inspection page using one database snapshot."""

from mycount.interface.DbMgr import DbMgr
from mycount.interface.IsoForestDb import IsoForestDb
from mycount.interface.VisitDb import VisitDb


class ReadIsoForest:
    def read(self, run_id: int | None = None) -> dict[str, object]:
        db = DbMgr()
        try:
            with db.transaction(read_only=True):
                store = IsoForestDb(db)
                runs = store.recent_runs()
                selected = store.active_run() if run_id is None else store.run(run_id)
                if run_id is not None and selected is None:
                    raise ValueError("IsoForest run not found.")
                observations = store.observations(selected["run_id"]) if selected is not None else []
                first = VisitDb(db).first_visit_at()
            return {"runs": runs, "selected": selected, "observations": observations,
                    "first_visit_at": first}
        finally:
            db.close()
