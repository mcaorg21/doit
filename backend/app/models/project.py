from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Project(BaseModel):
    id: str
    name: str
    createdAt: datetime
    updatedAt: datetime


class ProjectCreate(BaseModel):
    name: str


class ProjectUpdate(BaseModel):
    name: str


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
