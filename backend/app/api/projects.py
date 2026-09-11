from fastapi import APIRouter

from app.models.project import Project, ProjectCreate, ProjectSummary, ProjectUpdate
from app.storage import project_store

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectSummary])
def list_projects():
    return project_store.list_projects_with_counts()


@router.post("", response_model=Project)
def create_project(payload: ProjectCreate):
    return project_store.create_project(payload)


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str):
    return project_store.get_project(project_id)


@router.patch("/{project_id}", response_model=Project)
def update_project(project_id: str, payload: ProjectUpdate):
    return project_store.update_project(project_id, payload)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str):
    project_store.delete_project(project_id)
