from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Project(BaseModel):
    id: str
    name: str
    createdAt: datetime
    updatedAt: datetime


class ProjectSummary(Project):
    """GET /api/projects' response shape — adds workflowCount, computed on the fly
    from the project's workflows/ folder rather than stored on Project itself (so it
    never gets baked into project.json on a write that has nothing to do with
    workflows, e.g. a rename). Lets the projects list page offer a one-click delete
    only for projects that are actually empty."""

    workflowCount: int = 0


class ProjectCreate(BaseModel):
    name: str


class ProjectUpdate(BaseModel):
    name: str


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
