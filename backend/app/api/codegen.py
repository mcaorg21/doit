import json

from fastapi import APIRouter, HTTPException

from app.codegen.context import CodegenError
from app.codegen.engine import generate_script
from app.execution.runner import PreviewFailed, PreviewTimeout, run_preview_script
from app.models.workflow import VariablePreviewRequest, WorkflowGraph

router = APIRouter(prefix="/api/projects/{project_id}/workflows/{workflow_id}", tags=["codegen"])


@router.post("/generate-code")
def generate_code(project_id: str, workflow_id: str, payload: WorkflowGraph):
    try:
        code = generate_script(payload.nodes, payload.edges)
    except CodegenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"code": code}


@router.post("/preview-variable")
async def preview_variable(project_id: str, workflow_id: str, payload: VariablePreviewRequest):
    try:
        script = generate_script(payload.nodes, payload.edges, payload.nodeId, payload.variableName)
    except CodegenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        output = await run_preview_script(script)
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
