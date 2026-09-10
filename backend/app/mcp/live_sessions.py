"""In-memory registry of "live build" sessions — a real, paused Playwright process per
workflow_id, driven one simple statement at a time via the same pdb-over-stdin channel
the Element Inspector already uses (see app/execution/runner.py::send_input). This is
the execution layer behind the MCP demo_node tool (app/mcp/server.py): it lets an
external LLM perform a step for real (and see it fail/succeed) before that step gets
recorded as a node in the workflow.

Detection of success vs. failure was validated empirically against a real paused pdb
session (see the plan doc) rather than assumed from docs: the pdb prompt gets prefixed
onto whatever's echoed next, a bare expression's repr gets auto-printed (pdb's REPL
uses compile(..., mode="single")), and a caught exception is echoed with a "***"
prefix. A marker print sent right after the action line(s) always arrives (success or
failure — it's a separate statement that always runs), so it can't be used as the
success signal by itself; success is "marker arrived, and nothing captured before it
contained '***'".
"""

import asyncio
import time
import uuid
from dataclasses import dataclass

from app.codegen.context import CodegenContext
from app.codegen.engine import HEADER
from app.execution.run_manager import RunHandle
from app.execution.runner import send_input, start_run, stop_run
from app.nodes.open_browser import codegen_open_browser
from app.nodes.registry import NODE_REGISTRY

STEP_TIMEOUT_SECONDS = 35.0
"""Playwright's own default actionability timeout (30s) is what a genuinely-failing
click/fill/etc. takes to surface as a pdb error — this has to stay comfortably above
that, confirmed empirically: a shorter value here doesn't make Playwright itself give
up any sooner, it just makes THIS function report a false timeout while the action is
still silently retrying in the background, and then the next demo_node call's input
gets queued behind a process that hasn't reached its pdb prompt yet."""
BOOTSTRAP_TIMEOUT_SECONDS = 25.0


class LiveSessionError(Exception):
    """Raised for live-session lifecycle problems (already running, not found)."""


@dataclass
class LiveSession:
    workflow_id: str
    project_id: str
    handle: RunHandle
    browser_var: str
    target_var: str = "page"
    in_loop: bool = False
    last_node_id: str | None = None
    """The most recently persisted node in this session — demo_node auto-connects a
    new node after this one. Set by the caller (app/mcp/server.py) once it's actually
    persisted the node, not by this module."""


_sessions: dict[str, LiveSession] = {}


def get_session(workflow_id: str) -> LiveSession | None:
    return _sessions.get(workflow_id)


async def _execute_and_detect(handle: RunHandle, lines: list[str], timeout: float) -> tuple[bool, list[str]]:
    """Sends each of `lines` to the paused process, then a marker print, then watches
    the run's own log queue until the marker shows up. NOTE: this drains
    handle.queue — nothing else may also be consuming it (a live-session's run_id is
    never meant to be watched via /ws/runs/{run_id} at the same time)."""
    marker = f"__MCP_STEP_{uuid.uuid4().hex[:8]}__"
    for line in lines:
        await send_input(handle, line)
    await send_input(handle, f'print("{marker}")')

    captured: list[str] = []
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            captured.append(f"(timed out after {timeout:g}s waiting for a response)")
            return False, captured
        try:
            log_line = await asyncio.wait_for(handle.queue.get(), timeout=remaining)
        except asyncio.TimeoutError:
            captured.append(f"(timed out after {timeout:g}s waiting for a response)")
            return False, captured
        if log_line is None:
            captured.append("(the live session's browser process exited unexpectedly)")
            return False, captured
        text = log_line.text
        if marker in text:
            ok = not any("***" in c for c in captured)
            return ok, captured
        captured.append(text)


async def start_session(project_id: str, workflow_id: str, headless: bool, browser_channel: str) -> LiveSession:
    if workflow_id in _sessions:
        raise LiveSessionError(
            f"A live session is already running for workflow '{workflow_id}' — call finish_live_session first"
        )

    # profileName is deliberately left unset for live sessions (v1 keeps this simple:
    # always a plain browser.new_page(), no persistent profile support here) — mirrors
    # browser_var_after_open_browser's own "no profile -> 'browser'" branch.
    ctx = CodegenContext(
        node_id="bootstrap",
        params={"headless": headless, "browserChannel": browser_channel},
        in_loop=False,
        project_id=project_id,
        workflow_id=workflow_id,
        browser_var=None,
        target_var="page",
        has_breakpoints=True,
        node_label="Open Browser",
    )
    fragment = codegen_open_browser(ctx)
    script = f"{HEADER}\n{fragment}\n    breakpoint()\n"

    handle = await start_run(project_id, workflow_id, script)
    session = LiveSession(workflow_id=workflow_id, project_id=project_id, handle=handle, browser_var="browser", target_var="page")

    ok, captured = await _execute_and_detect(handle, [], timeout=BOOTSTRAP_TIMEOUT_SECONDS)
    if not ok:
        await stop_run(handle)
        raise LiveSessionError(f"Browser didn't finish opening in time. Captured: {captured}")

    _sessions[workflow_id] = session
    return session


def is_demoable(node_type: str) -> tuple[bool, str | None]:
    """Whether `node_type` can be live-demoed (a flat sequence of statements, no
    nested block) — see the plan doc's Achado crítico #2 for why block-opening node
    types (loop/if/browser_2captcha) can't go through this pdb-injection path, and why
    open_browser is the session bootstrap rather than a per-step demo."""
    if node_type == "open_browser":
        return False, "open_browser is the live session's bootstrap step — it's created by start_live_session, not demo_node"
    spec = NODE_REGISTRY.get(node_type)
    if spec is None:
        return False, f"Unknown node type '{node_type}'"
    if spec.is_branch:
        return False, f"'{node_type}' branches (true/false outputs) — use add_node + connect_nodes instead of demo_node"
    return True, None


async def run_demo_step(
    session: LiveSession, node_type: str, params: dict, node_label: str
) -> tuple[bool, list[str], CodegenContext]:
    """Runs one node's real codegen fragment against the live session. Returns
    (ok, captured_output, ctx) — ctx carries whatever browser_var_after/target_var_after
    would produce, for the caller to update session state on success (this function
    does not mutate `session` itself, so a failed step never leaves it half-updated)."""
    spec = NODE_REGISTRY[node_type]
    ctx = CodegenContext(
        node_id="demo",
        params=params,
        in_loop=session.in_loop,
        project_id=session.project_id,
        workflow_id=session.workflow_id,
        browser_var=session.browser_var,
        target_var=session.target_var,
        has_breakpoints=True,
        node_label=node_label,
    )
    opens = spec.opens_block(ctx) if callable(spec.opens_block) else spec.opens_block
    if opens:
        raise LiveSessionError(f"'{node_type}' opens a nested block with these params — not demoable live, use add_node instead")

    fragment = spec.codegen(ctx)
    lines = [line for line in fragment.splitlines() if line.strip()]
    ok, captured = await _execute_and_detect(session.handle, lines, timeout=STEP_TIMEOUT_SECONDS)
    return ok, captured, ctx


async def finish_session(workflow_id: str) -> bool:
    session = _sessions.pop(workflow_id, None)
    if session is None:
        return False
    close_call = "context.close()" if session.browser_var == "context" else "browser.close()"
    try:
        await send_input(session.handle, close_call)
        await asyncio.sleep(0.3)
    except Exception:
        pass
    await stop_run(session.handle)
    return True
