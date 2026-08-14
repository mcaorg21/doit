from fastapi import APIRouter, HTTPException

from app.models.llm_import import ReconstructPythonRequest, ReconstructPythonResponse
from app.services.workflow_reconstructor import ReconstructionError, reconstruct_workflow

router = APIRouter(prefix="/api/projects/{project_id}/workflows", tags=["llm-import"])


@router.post("/import-python/reconstruct", response_model=ReconstructPythonResponse)
def reconstruct_python_import(project_id: str, payload: ReconstructPythonRequest):
    try:
        return reconstruct_workflow(project_id, payload.code, payload.credentialId)
    except ReconstructionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
