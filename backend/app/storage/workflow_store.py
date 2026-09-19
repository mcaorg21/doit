from fastapi import HTTPException

from app.config import workflows_dir
from app.models.workflow import Workflow, WorkflowCreate, WorkflowImport, WorkflowSave
from app.models.project import now_utc
from app.storage import project_store
from app.storage.ids import gen_id


def _workflow_file(project_id: str, workflow_id: str):
    return workflows_dir(project_id) / f"{workflow_id}.json"


def _workflow_notes_file(project_id: str, workflow_id: str):
    # A real sibling .md file next to <workflow_id>.json — not a field inside the
    # workflow's own JSON — so it's directly readable/editable as plain markdown by
    # a coding agent's own file tools (or a human in a text editor), not just through
    # this app's API. Deliberately no per-run isolation (unlike temp_files_dir/
    # cookies_dir): this is human-written guidance for the workflow itself, the same
    # one document regardless of which run reads it. This is the "Instructions" half
    # of the split with _workflow_experience_file below — see that function's
    # docstring for why they're two separate files rather than one.
    return workflows_dir(project_id) / f"{workflow_id}.md"


def _workflow_experience_file(project_id: str, workflow_id: str):
    # A second sibling .md, deliberately separate from _workflow_notes_file above:
    # that one is the human-written spec for what this workflow should do
    # ("Instructions"), edited by hand and rarely touched by an agent. This one is
    # the AI-accumulated build history ("Experiência Adquirida") — session summaries
    # appended by write_workflow_experience every time an agent finishes a build/edit
    # session. Splitting them out means "Pegar experiência de outro workflow" (the
    # reference-workflow picker) can migrate specifically the LEARNED patterns from a
    # sibling workflow instead of its (possibly unrelated) instructions.
    return workflows_dir(project_id) / f"{workflow_id}.experience.md"


def get_workflow_notes(project_id: str, workflow_id: str) -> str:
    get_workflow(project_id, workflow_id)  # 404 if the workflow itself doesn't exist
    nfile = _workflow_notes_file(project_id, workflow_id)
    return nfile.read_text(encoding="utf-8") if nfile.exists() else ""


def set_workflow_notes(project_id: str, workflow_id: str, notes: str) -> None:
    get_workflow(project_id, workflow_id)  # 404 if the workflow itself doesn't exist
    nfile = _workflow_notes_file(project_id, workflow_id)
    if not notes.strip():
        # Don't leave an empty .md file sitting around once the human clears it out.
        if nfile.exists():
            nfile.unlink()
        return
    workflows_dir(project_id).mkdir(parents=True, exist_ok=True)
    nfile.write_text(notes, encoding="utf-8")


def get_workflow_experience(project_id: str, workflow_id: str) -> str:
    get_workflow(project_id, workflow_id)  # 404 if the workflow itself doesn't exist
    efile = _workflow_experience_file(project_id, workflow_id)
    return efile.read_text(encoding="utf-8") if efile.exists() else ""


def set_workflow_experience(project_id: str, workflow_id: str, experience: str) -> None:
    get_workflow(project_id, workflow_id)  # 404 if the workflow itself doesn't exist
    efile = _workflow_experience_file(project_id, workflow_id)
    if not experience.strip():
        if efile.exists():
            efile.unlink()
        return
    workflows_dir(project_id).mkdir(parents=True, exist_ok=True)
    efile.write_text(experience, encoding="utf-8")


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
    update: dict = {"published": published, "updatedAt": now_utc()}
    if published:
        # A fresh publish is the user saying "this is fixed now" — clear any stale
        # error flag from a previous unattended failure so the button goes back to a
        # plain Published state instead of staying red.
        update["hasError"] = False
    updated = existing.model_copy(update=update)
    _workflow_file(project_id, workflow_id).write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    project_store.touch_project(project_id)
    _resync_triggers(project_id, updated)
    return updated


def set_node_result_examples(project_id: str, workflow_id: str, results: dict[str, dict[str, object]]) -> Workflow | None:
    """Merges captured producesVariable example values onto matching nodes, keyed by
    node id then param key (see app/codegen/engine.py's _result_capture_lines and
    app/execution/runner.py's _stream_output, which calls this once a real Run
    finishes). A surgical per-node merge — like set_error_state — rather than a full
    save, since a Run can take a while and the graph itself may have been edited (or
    nodes deleted) by the time it finishes; ids no longer present are just skipped.
    Returns None (no-op, no write) if none of the captured node ids still exist."""
    existing = get_workflow(project_id, workflow_id)
    changed = False
    new_nodes = []
    for node in existing.nodes:
        captured = results.get(node.id)
        if captured:
            node = node.model_copy(update={"resultExamples": {**node.resultExamples, **captured}})
            changed = True
        new_nodes.append(node)
    if not changed:
        return None
    updated = existing.model_copy(update={"nodes": new_nodes, "updatedAt": now_utc()})
    _workflow_file(project_id, workflow_id).write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    return updated


def set_error_state(project_id: str, workflow_id: str, has_error: bool) -> Workflow:
    """Flags (or clears) hasError without touching published — used by
    app/execution/runner.py when an unattended (Schedule/Webhook) run fails, right
    before it also unpublishes via set_published above."""
    existing = get_workflow(project_id, workflow_id)
    updated = existing.model_copy(update={"hasError": has_error, "updatedAt": now_utc()})
    _workflow_file(project_id, workflow_id).write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    project_store.touch_project(project_id)
    return updated


def duplicate_workflow(project_id: str, workflow_id: str) -> Workflow:
    existing = get_workflow(project_id, workflow_id)
    new_id = gen_id("wf")
    ts = now_utc()
    duplicate = existing.model_copy(
        update={
            "id": new_id,
            "name": f"{existing.name} (copy)",
            "createdAt": ts,
            "updatedAt": ts,
            "published": False,
            "hasError": False,
        }
    )
    workflows_dir(project_id).mkdir(parents=True, exist_ok=True)
    _workflow_file(project_id, new_id).write_text(duplicate.model_dump_json(indent=2), encoding="utf-8")
    existing_notes = _workflow_notes_file(project_id, workflow_id)
    if existing_notes.exists():
        _workflow_notes_file(project_id, new_id).write_text(existing_notes.read_text(encoding="utf-8"), encoding="utf-8")
    existing_experience = _workflow_experience_file(project_id, workflow_id)
    if existing_experience.exists():
        _workflow_experience_file(project_id, new_id).write_text(
            existing_experience.read_text(encoding="utf-8"), encoding="utf-8"
        )
    project_store.touch_project(project_id)
    return duplicate


def delete_workflow(project_id: str, workflow_id: str) -> None:
    wfile = _workflow_file(project_id, workflow_id)
    if not wfile.exists():
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    wfile.unlink()
    notes_file = _workflow_notes_file(project_id, workflow_id)
    if notes_file.exists():
        notes_file.unlink()
    experience_file = _workflow_experience_file(project_id, workflow_id)
    if experience_file.exists():
        experience_file.unlink()
    project_store.touch_project(project_id)

    from app.execution import scheduler, webhook_registry

    scheduler.remove_workflow_job(workflow_id)
    webhook_registry.remove_workflow(workflow_id)
