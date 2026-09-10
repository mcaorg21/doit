import json

from fastapi import APIRouter, HTTPException

from app.codegen.context import CodegenError
from app.codegen.engine import generate_script
from app.execution.runner import PreviewFailed, PreviewTimeout, run_preview_script
from app.models.workflow import VariablePreviewRequest, WFNode, WorkflowGraph

router = APIRouter(prefix="/api/projects/{project_id}/workflows/{workflow_id}", tags=["codegen"])

_PREVIEW_TIMEOUT_BUFFER = 10.0
"""Extra seconds on top of an http_request node's own Timeout, for script startup
(imports, Python interpreter boot) that isn't part of the HTTP call itself."""
_UNBOUNDED_PREVIEW_TIMEOUT = 60.0
"""Bound used when the node's Timeout is set to 0 ("no timeout") — Run Preview waits
synchronously for the subprocess, so it can't honor a truly unbounded request."""


def _preview_timeout(nodes: list[WFNode], node_id: str) -> float:
    """Run Preview executes the generated script and waits for it, so it needs its own
    bound. For an http_request node this should track the Timeout the user configured
    on that node (backend/app/nodes/http_request.py) instead of the old fixed 20s,
    which was shorter than some real APIs need and unrelated to what the node itself
    was configured to wait for."""
    node = next((n for n in nodes if n.id == node_id), None)
    if node is None or node.type != "http_request":
        return 20.0
    value = node.params.get("timeoutSeconds")
    try:
        seconds = float(value) if value not in (None, "") else 30.0
    except (TypeError, ValueError):
        seconds = 30.0
    if seconds <= 0:
        return _UNBOUNDED_PREVIEW_TIMEOUT
    return seconds + _PREVIEW_TIMEOUT_BUFFER


@router.post("/generate-code")
def generate_code(project_id: str, workflow_id: str, payload: WorkflowGraph):
    try:
        code = generate_script(payload.nodes, payload.edges, project_id, start_node_id=payload.startNodeId)
    except CodegenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"code": code}


@router.post("/preview-variable")
async def preview_variable(project_id: str, workflow_id: str, payload: VariablePreviewRequest):
    try:
        script = generate_script(
            payload.nodes, payload.edges, project_id, payload.nodeId, payload.variableName, payload.startNodeId
        )
    except CodegenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        output = await run_preview_script(script, timeout=_preview_timeout(payload.nodes, payload.nodeId))
    except PreviewTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except PreviewFailed as exc:
        raise HTTPException(status_code=422, detail=_tail(exc.output)) from exc

    for line in reversed(output.splitlines()):
        if line.startswith("__PREVIEW__"):
            raw = line[len("__PREVIEW__") :]
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                raise HTTPException(status_code=500, detail=f"Couldn't parse preview output: {raw!r}")
            return {"value": value}

    raise HTTPException(status_code=500, detail=_tail(output) or "No output was produced")


def _tail(text: str, max_lines: int = 20) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-max_lines:])
