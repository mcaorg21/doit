import asyncio
from dataclasses import dataclass, field

from app.models.run import LogLine, RunRecord


@dataclass
class RunHandle:
    run_id: str
    project_id: str
    workflow_id: str
    record: RunRecord
    queue: "asyncio.Queue[LogLine | None]" = field(default_factory=asyncio.Queue)
    process: asyncio.subprocess.Process | None = None
    cancelled: bool = False


_active_runs: dict[str, RunHandle] = {}


def register_run(handle: RunHandle) -> None:
    _active_runs[handle.run_id] = handle


def get_run_handle(run_id: str) -> RunHandle | None:
    return _active_runs.get(run_id)
