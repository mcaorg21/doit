import asyncio
from datetime import datetime, timezone

from app.config import GENERATED_SCRIPTS_DIR, PYTHON_EXECUTABLE
from app.execution.run_manager import RunHandle, register_run
from app.models.run import LogLine, RunRecord, RunStatus
from app.storage import run_store
from app.storage.ids import gen_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def start_run(project_id: str, workflow_id: str, script: str) -> RunHandle:
    run_id = gen_id("run")
    script_path = GENERATED_SCRIPTS_DIR / f"{workflow_id}_{run_id}.py"
    script_path.write_text(script, encoding="utf-8")

    record = RunRecord(
        id=run_id,
        workflowId=workflow_id,
        startedAt=_now(),
        status=RunStatus.running,
        scriptPath=str(script_path),
    )
    handle = RunHandle(run_id=run_id, project_id=project_id, workflow_id=workflow_id, record=record)

    process = await asyncio.create_subprocess_exec(
        PYTHON_EXECUTABLE,
        "-u",  # unbuffered stdout/stderr — without this, Python fully buffers output
        # when it isn't attached to a real terminal (i.e. always, here, since stdout is
        # a pipe), so every print() from the script sits in a buffer and only reaches
        # us in one burst at process exit instead of streaming live as each node runs.
        str(script_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    handle.process = process
    register_run(handle)
    # Persisted immediately (not just once it finishes) so a run shows up in
    # Executions the moment it starts, with status "running" — otherwise a run that
    # never finishes (e.g. a scheduled/webhook-triggered run that hits a Pause node's
    # breakpoint(), which nothing unattended can ever send "continue" to) stays
    # invisible forever, since run_store.save_run() below was previously the only
    # write, called only after the process actually exits.
    run_store.save_run(project_id, record)
    asyncio.create_task(_stream_output(handle))
    return handle


class PreviewTimeout(Exception):
    """Raised when a variable-preview script doesn't finish within the timeout."""


class PreviewFailed(Exception):
    """Raised when a variable-preview script exits non-zero (e.g. selector not found)."""

    def __init__(self, output: str):
        super().__init__(output)
        self.output = output


async def run_preview_script(script: str, timeout: float = 20.0) -> str:
    """Runs a (usually truncated) script to completion and returns its raw stdout —
    used by the variable-preview feature, which needs the real value of a variable at
    a specific point in the graph, not a tracked/streamed run."""
    run_id = gen_id("preview")
    script_path = GENERATED_SCRIPTS_DIR / f"{run_id}.py"
    script_path.write_text(script, encoding="utf-8")

    process = await asyncio.create_subprocess_exec(
        PYTHON_EXECUTABLE,
        "-u",
        str(script_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise PreviewTimeout(f"Preview didn't finish within {timeout:.0f}s")

    output = stdout.decode(errors="replace")
    if process.returncode != 0:
        raise PreviewFailed(output)
    return output


async def send_input(handle: RunHandle, text: str) -> None:
    """Writes a line of text to a running script's stdin — used to interact with pdb
    once it's paused at a `breakpoint()` inserted by a workflow edge marked as a
    breakpoint (any pdb command: c, n, s, p <expr>, l, ...). Since we only see the
    process's stdout line-by-line, pdb's un-terminated "(Pdb) " prompt never shows up
    in the log on its own; the log simply going quiet while status is still "running"
    is the signal that it's likely paused."""
    process = handle.process
    if process is None or process.stdin is None or process.stdin.is_closing():
        return
    process.stdin.write(text.encode() + b"\n")
    await process.stdin.drain()


async def send_continue(handle: RunHandle) -> None:
    await send_input(handle, "c")


async def stop_run(handle: RunHandle) -> None:
    """Force-kills a running script (e.g. Ctrl+C from the Run panel). Since the script
    is killed abruptly rather than given a chance to run its own cleanup, a Playwright
    browser it launched may be left open — closing it is left to the user in that case,
    the same rough edge you'd hit killing a real terminal automation script."""
    process = handle.process
    if process is None or process.returncode is not None:
        return
    handle.cancelled = True
    process.kill()


async def _stream_output(handle: RunHandle) -> None:
    process = handle.process
    assert process is not None and process.stdout is not None

    async for raw_line in process.stdout:
        text = raw_line.decode(errors="replace").rstrip("\n")
        line = LogLine(ts=_now(), level="info", text=text)
        handle.record.logLines.append(line)
        await handle.queue.put(line)
        # Keeps the persisted record's log up to date while still running — matters
        # most for a run stuck at a Pause breakpoint (see the note in start_run): the
        # Executions report should show what it actually did before hanging, not an
        # empty log until (if ever) it finishes.
        run_store.save_run(handle.project_id, handle.record)

    exit_code = await process.wait()
    handle.record.finishedAt = _now()
    handle.record.exitCode = exit_code
    if handle.cancelled:
        handle.record.status = RunStatus.cancelled
    else:
        handle.record.status = RunStatus.success if exit_code == 0 else RunStatus.error
    run_store.save_run(handle.project_id, handle.record)
    await handle.queue.put(None)
