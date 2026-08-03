from fastapi import APIRouter

from app.models.workflow import Workflow, WorkflowCreate, WorkflowSave
from app.storage import workflow_store

router = APIRouter(prefix="/api/projects/{project_id}/workflows", tags=["workflows"])


@router.get("", response_model=list[Workflow])
def list_workflows(project_id: str):
    return workflow_store.list_workflows(project_id)


@router.post("", response_model=Workflow)
def create_workflow(project_id: str, payload: WorkflowCreate):
    return workflow_store.create_workflow(project_id, payload)


@router.get("/{workflow_id}", response_model=Workflow)
def get_workflow(project_id: str, workflow_id: str):
    return workflow_store.get_workflow(project_id, workflow_id)


@router.put("/{workflow_id}", response_model=Workflow)
def save_workflow(project_id: str, workflow_id: str, payload: WorkflowSave):
    return workflow_store.save_workflow(project_id, workflow_id, payload)


@router.delete("/{workflow_id}", status_code=204)
def delete_workflow(project_id: str, workflow_id: str):
    workflow_store.delete_workflow(project_id, workflow_id)
