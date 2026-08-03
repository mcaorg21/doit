from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.codegen.context import CodegenError
from app.codegen.engine import generate_script
from app.execution.run_manager import get_run_handle
from app.execution.runner import send_continue, send_input, start_run, stop_run
from app.models.run import RunRecord
from app.models.workflow import WorkflowGraph
from app.storage import run_store


class RunInput(BaseModel):
    text: str

router = APIRouter(tags=["runs"])


@router.post("/api/projects/{project_id}/workflows/{workflow_id}/run")
async def run_workflow(project_id: str, workflow_id: str, payload: WorkflowGraph):
    try:
        script = generate_script(payload.nodes, payload.edges)
    except CodegenError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    handle = await start_run(project_id, workflow_id, script)
    return {"runId": handle.run_id}


@router.post("/api/runs/{run_id}/continue")
async def continue_run(run_id: str):
    handle = get_run_handle(run_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found or already finished")
    await send_continue(handle)
    return {"ok": True}


@router.post("/api/runs/{run_id}/input")
async def send_run_input(run_id: str, payload: RunInput):
    handle = get_run_handle(run_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found or already finished")
    await send_input(handle, payload.text)
    return {"ok": True}


@router.post("/api/runs/{run_id}/stop")
async def stop_run_endpoint(run_id: str):
    handle = get_run_handle(run_id)
    if handle is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found or already finished")
    await stop_run(handle)
    return {"ok": True}


@router.get("/api/projects/{project_id}/runs", response_model=list[RunRecord])
def list_runs(project_id: str):
    return run_store.list_runs(project_id)


@router.get("/api/projects/{project_id}/runs/{run_id}", response_model=RunRecord)
def get_run(project_id: str, run_id: str):
    handle = get_run_handle(run_id)
    if handle is not None:
        return handle.record
    return run_store.get_run(project_id, run_id)


@router.websocket("/ws/runs/{run_id}")
async def run_log_stream(websocket: WebSocket, run_id: str):
    await websocket.accept()
    handle = get_run_handle(run_id)
    if handle is None:
        await websocket.send_json({"type": "error", "detail": f"Run '{run_id}' not found or already finished"})
        await websocket.close()
        return

    try:
        for line in handle.record.logLines:
            await websocket.send_json({"type": "log", **line.model_dump(mode="json")})

        while True:
            line = await handle.queue.get()
            if line is None:
                await websocket.send_json(
                    {
                        "type": "done",
                        "status": handle.record.status.value,
                        "exitCode": handle.record.exitCode,
                    }
                )
                break
            await websocket.send_json({"type": "log", **line.model_dump(mode="json")})
    except WebSocketDisconnect:
        return

    await websocket.close()
