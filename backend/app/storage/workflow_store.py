from fastapi import HTTPException

from app.config import workflows_dir
from app.models.workflow import Workflow, WorkflowCreate, WorkflowSave
from app.models.project import now_utc
from app.storage import project_store
from app.storage.ids import gen_id


def _workflow_file(project_id: str, workflow_id: str):
    return workflows_dir(project_id) / f"{workflow_id}.json"


def list_workflows(project_id: str) -> list[Workflow]:
    project_store.get_project(project_id)  # 404 if project missing
    wdir = workflows_dir(project_id)
    if not wdir.exists():
        return []
    workflows = []
    for child in sorted(wdir.iterdir()):
        if child.suffix == ".json":
            workflows.append(Workflow.model_validate_json(child.read_text(encoding="utf-8")))
    workflows.sort(key=lambda w: w.updatedAt, reverse=True)
    return workflows


def get_workflow(project_id: str, workflow_id: str) -> Workflow:
    wfile = _workflow_file(project_id, workflow_id)
    if not wfile.exists():
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return Workflow.model_validate_json(wfile.read_text(encoding="utf-8"))


def create_workflow(project_id: str, payload: WorkflowCreate) -> Workflow:
    project_store.get_project(project_id)  # 404 if project missing
    workflow_id = gen_id("wf")
    ts = now_utc()
    workflow = Workflow(
        id=workflow_id,
        projectId=project_id,
        name=payload.name,
        createdAt=ts,
        updatedAt=ts,
        nodes=[],
        edges=[],
    )
    workflows_dir(project_id).mkdir(parents=True, exist_ok=True)
    _workflow_file(project_id, workflow_id).write_text(workflow.model_dump_json(indent=2), encoding="utf-8")
    project_store.touch_project(project_id)
    return workflow


def save_workflow(project_id: str, workflow_id: str, payload: WorkflowSave) -> Workflow:
    existing = get_workflow(project_id, workflow_id)
    updated = existing.model_copy(
        update={
            "name": payload.name,
            "nodes": payload.nodes,
            "edges": payload.edges,
            "updatedAt": now_utc(),
        }
    )
    _workflow_file(project_id, workflow_id).write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    project_store.touch_project(project_id)
    return updated


def delete_workflow(project_id: str, workflow_id: str) -> None:
    wfile = _workflow_file(project_id, workflow_id)
    if not wfile.exists():
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    wfile.unlink()
    project_store.touch_project(project_id)
