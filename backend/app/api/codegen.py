from fastapi import APIRouter, HTTPException

from app.codegen.context import CodegenError
from app.codegen.engine import generate_script
from app.models.workflow import WorkflowGraph

router = APIRouter(prefix="/api/projects/{project_id}/workflows/{workflow_id}", tags=["codegen"])


@router.post("/generate-code")
def generate_code(project_id: str, workflow_id: str, payload: WorkflowGraph):
    try:
        code = generate_script(payload.nodes, payload.edges)
    except CodegenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"code": code}
