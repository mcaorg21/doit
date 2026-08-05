from fastapi import APIRouter, HTTPException

from app.execution import triggers
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


@router.post("/{workflow_id}/duplicate", response_model=Workflow)
def duplicate_workflow(project_id: str, workflow_id: str):
    return workflow_store.duplicate_workflow(project_id, workflow_id)


@router.post("/{workflow_id}/publish", response_model=Workflow)
def publish_workflow(project_id: str, workflow_id: str):
    workflow = workflow_store.get_workflow(project_id, workflow_id)
    try:
        triggers.validate_publishable(workflow)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return workflow_store.set_published(project_id, workflow_id, True)


@router.post("/{workflow_id}/unpublish", response_model=Workflow)
def unpublish_workflow(project_id: str, workflow_id: str):
    return workflow_store.set_published(project_id, workflow_id, False)


@router.delete("/{workflow_id}", status_code=204)
def delete_workflow(project_id: str, workflow_id: str):
    workflow_store.delete_workflow(project_id, workflow_id)
