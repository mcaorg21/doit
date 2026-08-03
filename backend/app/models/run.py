from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    running = "running"
    success = "success"
    error = "error"
    cancelled = "cancelled"


class LogLine(BaseModel):
    ts: datetime
    level: str = "info"
    text: str


class RunRecord(BaseModel):
    id: str
    workflowId: str
    startedAt: datetime
    finishedAt: datetime | None = None
    status: RunStatus = RunStatus.running
    exitCode: int | None = None
    scriptPath: str
    logLines: list[LogLine] = Field(default_factory=list)
