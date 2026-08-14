from fastapi import HTTPException

from app.config import workflows_dir
from app.models.workflow import Workflow, WorkflowCreate, WorkflowImport, WorkflowSave
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


def _validate_folder(project_id: str, folder_id: str | None) -> None:
    if folder_id is None:
        return
    from app.storage import folder_store

    if not any(f.id == folder_id for f in folder_store.list_folders(project_id)):
        raise HTTPException(status_code=404, detail=f"Folder '{folder_id}' not found")


def create_workflow(project_id: str, payload: WorkflowCreate) -> Workflow:
    project_store.get_project(project_id)  # 404 if project missing
    _validate_folder(project_id, payload.folderId)
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
        folderId=payload.folderId,
    )
    workflows_dir(project_id).mkdir(parents=True, exist_ok=True)
    _workflow_file(project_id, workflow_id).write_text(workflow.model_dump_json(indent=2), encoding="utf-8")
    project_store.touch_project(project_id)
    return workflow


def import_workflow(project_id: str, payload: WorkflowImport) -> Workflow:
    """Creates a new workflow from an exported graph (see the frontend's Export
    button). Always starts unpublished, even if the exported file came from a
    published workflow — an imported Schedule/Webhook trigger shouldn't silently
    start firing before the user has had a chance to review it."""
    project_store.get_project(project_id)  # 404 if project missing
    _validate_folder(project_id, payload.folderId)
    workflow_id = gen_id("wf")
    ts = now_utc()
    workflow = Workflow(
        id=workflow_id,
        projectId=project_id,
        name=payload.name,
        createdAt=ts,
        updatedAt=ts,
        nodes=payload.nodes,
        edges=payload.edges,
        published=False,
        folderId=payload.folderId,
        startNodeId=payload.startNodeId,
    )
    workflows_dir(project_id).mkdir(parents=True, exist_ok=True)
    _workflow_file(project_id, workflow_id).write_text(workflow.model_dump_json(indent=2), encoding="utf-8")
    project_store.touch_project(project_id)
    return workflow


def put_workflow(project_id: str, workflow: Workflow) -> None:
    """Writes a workflow verbatim, preserving its id/timestamps as-is — used by
    restore (app/services/backup_orchestrator.py). Still resyncs
    scheduler/webhook registration so a restored published workflow with a
    Schedule/Webhook trigger resumes firing immediately, same as save_workflow()."""
    workflows_dir(project_id).mkdir(parents=True, exist_ok=True)
    _workflow_file(project_id, workflow.id).write_text(workflow.model_dump_json(indent=2), encoding="utf-8")
    _resync_triggers(project_id, workflow)


def _resync_triggers(project_id: str, workflow: Workflow) -> None:
    # Local import: scheduler.py/webhook_registry.py import this module too (to reload
    # the workflow fresh when a job/webhook fires), so importing them at module load
    # time here would be circular.
    from app.execution import scheduler, webhook_registry

    scheduler.sync_workflow(project_id, workflow)
    webhook_registry.sync_workflow(project_id, workflow)


def save_workflow(project_id: str, workflow_id: str, payload: WorkflowSave) -> Workflow:
    existing = get_workflow(project_id, workflow_id)
    updated = existing.model_copy(
        update={
            "name": payload.name,
            "nodes": payload.nodes,
            "edges": payload.edges,
            "startNodeId": payload.startNodeId,
            "updatedAt": now_utc(),
        }
    )
    _workflow_file(project_id, workflow_id).write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    project_store.touch_project(project_id)
    # Keeps a published workflow's trigger in sync with edits (e.g. changed cron
    # expression or webhook path) without requiring an unpublish/republish round-trip.
    _resync_triggers(project_id, updated)
    return updated


def move_workflow(project_id: str, workflow_id: str, folder_id: str | None) -> Workflow:
    _validate_folder(project_id, folder_id)
    existing = get_workflow(project_id, workflow_id)
    updated = existing.model_copy(update={"folderId": folder_id, "updatedAt": now_utc()})
    _workflow_file(project_id, workflow_id).write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    project_store.touch_project(project_id)
    return updated


def set_published(project_id: str, workflow_id: str, published: bool) -> Workflow:
    existing = get_workflow(project_id, workflow_id)
    updated = existing.model_copy(update={"published": published, "updatedAt": now_utc()})
    _workflow_file(project_id, workflow_id).write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    project_store.touch_project(project_id)
    _resync_triggers(project_id, updated)
    return updated


def duplicate_workflow(project_id: str, workflow_id: str) -> Workflow:
    existing = get_workflow(project_id, workflow_id)
    new_id = gen_id("wf")
    ts = now_utc()
    duplicate = existing.model_copy(
        update={"id": new_id, "name": f"{existing.name} (copy)", "createdAt": ts, "updatedAt": ts, "published": False}
    )
    workflows_dir(project_id).mkdir(parents=True, exist_ok=True)
    _workflow_file(project_id, new_id).write_text(duplicate.model_dump_json(indent=2), encoding="utf-8")
    project_store.touch_project(project_id)
    return duplicate


def delete_workflow(project_id: str, workflow_id: str) -> None:
    wfile = _workflow_file(project_id, workflow_id)
    if not wfile.exists():
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    wfile.unlink()
    project_store.touch_project(project_id)

    from app.execution import scheduler, webhook_registry

    scheduler.remove_workflow_job(workflow_id)
    webhook_registry.remove_workflow(workflow_id)
