from fastapi import HTTPException

from app.config import runs_dir
from app.models.run import RunRecord


def _run_file(project_id: str, run_id: str):
    return runs_dir(project_id) / f"{run_id}.json"


def save_run(project_id: str, run: RunRecord) -> None:
    runs_dir(project_id).mkdir(parents=True, exist_ok=True)
    _run_file(project_id, run.id).write_text(run.model_dump_json(indent=2), encoding="utf-8")


def get_run(project_id: str, run_id: str) -> RunRecord:
    rfile = _run_file(project_id, run_id)
    if not rfile.exists():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return RunRecord.model_validate_json(rfile.read_text(encoding="utf-8"))


def list_runs(project_id: str) -> list[RunRecord]:
    rdir = runs_dir(project_id)
    if not rdir.exists():
        return []
    runs = []
    for child in sorted(rdir.iterdir()):
        if child.suffix == ".json":
            runs.append(RunRecord.model_validate_json(child.read_text(encoding="utf-8")))
    runs.sort(key=lambda r: r.startedAt, reverse=True)
    return runs
