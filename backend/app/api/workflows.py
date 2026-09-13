from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.execution import triggers, workflow_events
from app.mcp import voice_prompts
from app.models.workflow import Workflow, WorkflowCreate, WorkflowImport, WorkflowSave
from app.storage import workflow_store


class WorkflowMove(BaseModel):
    folderId: str | None = None


class WorkflowNotes(BaseModel):
    notes: str


class VoiceAnswer(BaseModel):
    questionId: str
    answer: str

router = APIRouter(prefix="/api/projects/{project_id}/workflows", tags=["workflows"])

# Separate, unprefixed router: the MCP server's live-build tools (app/mcp/server.py)
# publish node/edge mutations here so any open editor tab redraws without a manual
# refresh. Can't live on `router` above (it's prefixed with .../workflows), needs a
# flat /ws/workflows/{id} path matching the /ws/runs/{id} convention (app/api/runs.py)
# that the frontend dev-server proxy (frontend/vite.config.ts) already expects.
ws_router = APIRouter(tags=["workflow-events"])


@ws_router.websocket("/ws/workflows/{workflow_id}")
async def workflow_event_stream(websocket: WebSocket, workflow_id: str):
    await websocket.accept()
    queue = workflow_events.subscribe(workflow_id)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        workflow_events.unsubscribe(workflow_id, queue)


@router.get("", response_model=list[Workflow])
def list_workflows(project_id: str):
    return workflow_store.list_workflows(project_id)


@router.post("", response_model=Workflow)
def create_workflow(project_id: str, payload: WorkflowCreate):
    return workflow_store.create_workflow(project_id, payload)


@router.post("/import", response_model=Workflow)
def import_workflow(project_id: str, payload: WorkflowImport):
    return workflow_store.import_workflow(project_id, payload)


@router.get("/{workflow_id}", response_model=Workflow)
def get_workflow(project_id: str, workflow_id: str):
    return workflow_store.get_workflow(project_id, workflow_id)


@router.put("/{workflow_id}", response_model=Workflow)
def save_workflow(project_id: str, workflow_id: str, payload: WorkflowSave):
    return workflow_store.save_workflow(project_id, workflow_id, payload)


@router.post("/{workflow_id}/duplicate", response_model=Workflow)
def duplicate_workflow(project_id: str, workflow_id: str):
    return workflow_store.duplicate_workflow(project_id, workflow_id)


@router.post("/{workflow_id}/move", response_model=Workflow)
def move_workflow(project_id: str, workflow_id: str, payload: WorkflowMove):
    return workflow_store.move_workflow(project_id, workflow_id, payload.folderId)


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


@router.get("/{workflow_id}/notes", response_model=WorkflowNotes)
def get_workflow_notes(project_id: str, workflow_id: str):
    return WorkflowNotes(notes=workflow_store.get_workflow_notes(project_id, workflow_id))


@router.put("/{workflow_id}/notes", response_model=WorkflowNotes)
def set_workflow_notes(project_id: str, workflow_id: str, payload: WorkflowNotes):
    workflow_store.set_workflow_notes(project_id, workflow_id, payload.notes)
    return payload


@router.post("/{workflow_id}/voice-answer")
def submit_voice_answer(project_id: str, workflow_id: str, payload: VoiceAnswer):
    """Resolves a pending ask_human_voice MCP tool call (app/mcp/voice_prompts.py)
    with the human's transcribed answer — the REST half of the voice-guided build
    loop, called by the editor's "E agora?" prompt."""
    if not voice_prompts.answer(workflow_id, payload.questionId, payload.answer):
        raise HTTPException(status_code=404, detail="No matching pending question (it may have timed out or already been answered).")
    return {"ok": True}
