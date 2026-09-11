from fastapi import HTTPException

from app.models.workflow import WFNode, Workflow

# "METHOD:path" -> (project_id, workflow_id) — purely in-memory, rebuilt from disk at
# startup and kept in sync on every save/publish/delete (see sync_workflow below).
_registry: dict[str, tuple[str, str]] = {}


def _key(method: str, path: str) -> str:
    return f"{method.upper()}:{path.strip('/').lower()}"


def validate_webhook_node(node: WFNode) -> None:
    """Raises ValueError with a user-facing message when this Webhook trigger node
    isn't configured well enough to be published."""
    params = node.params or {}
    path = str(params.get("path") or "").strip().strip("/")
    if not path:
        raise ValueError("Webhook trigger needs a Path before it can be published")
    secret = str(params.get("secret") or "").strip().strip("/")
    if not secret:
        raise ValueError("Webhook trigger needs a Secret before it can be published (use the regenerate button)")


def _key_for_node(node: WFNode) -> str:
    params = node.params or {}
    method = str(params.get("method") or "POST").upper()
    path = str(params.get("path") or "").strip().strip("/")
    secret = str(params.get("secret") or "").strip().strip("/")
    return _key(method, f"{path}/{secret}")


def remove_workflow(workflow_id: str) -> None:
    for key in [k for k, v in _registry.items() if v[1] == workflow_id]:
        del _registry[key]


def sync_workflow(project_id: str, workflow: Workflow) -> None:
    """Adds/updates/removes this workflow's webhook registration to match its
    current published flag and Webhook trigger params. Called after every save,
    publish toggle, and once for every workflow at backend startup."""
    remove_workflow(workflow.id)
    if not workflow.published:
        return

    from app.execution.triggers import find_root_node

    root = find_root_node(workflow.nodes, workflow.edges, workflow.startNodeId)
    if root is None or root.type != "webhook_trigger":
        return
    try:
        validate_webhook_node(root)
    except ValueError as exc:
        print(f"[webhook] workflow '{workflow.name}' ({workflow.id}): {exc} — not registered")
        return

    key = _key_for_node(root)
    existing = _registry.get(key)
    if existing is not None and existing[1] != workflow.id:
        print(
            f"[webhook] workflow '{workflow.name}' ({workflow.id}): path {key!r} is already used by "
            f"another published workflow — not registered"
        )
        return

    _registry[key] = (project_id, workflow.id)
    print(f"[webhook] registered workflow '{workflow.name}' ({workflow.id}) at {key}")


def sync_all() -> None:
    from app.storage import project_store, workflow_store

    for project in project_store.list_projects():
        for workflow in workflow_store.list_workflows(project.id):
            sync_workflow(project.id, workflow)


async def trigger(method: str, path: str) -> dict:
    from app.codegen.context import CodegenError
    from app.codegen.engine import generate_script
    from app.execution.runner import start_run
    from app.storage import workflow_store

    entry = _registry.get(_key(method, path))
    if entry is None:
        raise HTTPException(status_code=404, detail=f"No published webhook at {method.upper()} /{path}")
    project_id, workflow_id = entry

    workflow = workflow_store.get_workflow(project_id, workflow_id)
    if not workflow.published:
        raise HTTPException(status_code=404, detail=f"No published webhook at {method.upper()} /{path}")

    try:
        script = generate_script(
            workflow.nodes, workflow.edges, project_id, start_node_id=workflow.startNodeId, workflow_id=workflow_id
        )
    except CodegenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    handle = await start_run(project_id, workflow_id, script, unattended=True)
    return {"runId": handle.run_id, "workflowId": workflow_id}
