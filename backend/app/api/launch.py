"""Editor shortcut buttons ("Abrir Terminal" / "Abrir Claude Desktop") that launch a
local app on THIS machine — the one running the backend. Only makes sense today,
while the backend runs on the same machine as the person clicking the button: once
this app moves to a shared server (see docs/mcp-connector.md), these endpoints would
launch a process on the SERVER, not the caller's machine, and since the rest of this
API has no authentication, anyone on the network could trigger them. Revisit (add
auth, or drop this feature) before that move — this is a deliberate, accepted
trade-off for now, not an oversight.
"""

import os
import re
import subprocess

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import REPO_ROOT

router = APIRouter(prefix="/api/launch", tags=["launch"])

_MCP_SERVER_NAME = "automation"
_MCP_URL = "http://127.0.0.1:8001/mcp"
"""Must match the host/port app/main.py's `mcp` is actually served on (see
package.json's server:dev script) — there's no shared single source of truth for
this today since the port is an uvicorn CLI arg, not app config."""

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class LaunchTerminalRequest(BaseModel):
    projectId: str | None = None
    workflowId: str | None = None


class LaunchResult(BaseModel):
    launched: bool
    detail: str | None = None
    notify: bool = False
    """Whether the frontend should actually show `detail` to the user — false for a
    routine, nothing-to-report success (e.g. the MCP server was already registered),
    so a normal click doesn't pop a modal just to say "everything's fine"."""


def _ensure_mcp_registered() -> tuple[bool, str]:
    """Registers this app's MCP server with the local `claude` CLI if it isn't
    already (checked via `claude mcp list`, matched by server name) — so a freshly
    opened terminal has the automation tools available immediately, without the user
    having to run `claude mcp add` by hand first. Best-effort: any failure here still
    lets the terminal open, just with a warning in the response."""
    try:
        listed = subprocess.run(
            ["claude", "mcp", "list"], capture_output=True, text=True, timeout=15, cwd=str(REPO_ROOT)
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Couldn't check registered MCP servers ({exc}) — is 'claude' on PATH?"

    if any(line.strip().startswith(f"{_MCP_SERVER_NAME}:") for line in listed.stdout.splitlines()):
        return True, "MCP server already registered"

    try:
        added = subprocess.run(
            ["claude", "mcp", "add", "--transport", "http", _MCP_SERVER_NAME, _MCP_URL],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(REPO_ROOT),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Couldn't register the MCP server: {exc}"

    if added.returncode != 0:
        return False, (added.stderr or added.stdout).strip() or "claude mcp add failed"
    return True, "MCP server registered"


def _validate_id(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    if not _SAFE_ID_RE.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid {label}")
    return value


def _initial_prompt(project_id: str | None, workflow_id: str | None) -> str | None:
    if not (project_id and workflow_id):
        return None
    return (
        f"Continue editando o workflow (project_id={project_id}, workflow_id={workflow_id}) "
        f"no app auto-mation via o MCP '{_MCP_SERVER_NAME}' ({_MCP_URL}). Comece chamando "
        f"get_workflow pra ver o que ja existe antes de continuar."
    )


@router.post("/terminal", response_model=LaunchResult)
def launch_terminal(payload: LaunchTerminalRequest):
    project_id = _validate_id(payload.projectId, "projectId")
    workflow_id = _validate_id(payload.workflowId, "workflowId")

    mcp_ok, mcp_detail = _ensure_mcp_registered()

    prompt = _initial_prompt(project_id, workflow_id)
    claude_cmd = f'claude "{prompt}"' if prompt else "claude"
    # `title ... & <cmd>` (no `start`, no nested `cmd /k` layer) — `cmd /c start
    # "title" cmd /k "..."` looks reasonable but is a known Windows minefield: `start`
    # treats the first quoted argument as a window title only under specific
    # conditions, and gets confused once a second layer of quotes (the ones around
    # the initial prompt) enters the mix — confirmed broken in practice (landed in
    # the wrong cwd and never ran `claude` at all). `cwd=` on Popen replaces the
    # `cd /d` entirely, and CREATE_NEW_CONSOLE is what actually pops a new window
    # (this process has no console of its own to inherit, e.g. when npm/uvicorn
    # itself wasn't started from an interactive terminal).
    full_cmd = f"title Claude Code - auto-mation & {claude_cmd}"
    try:
        subprocess.Popen(["cmd", "/k", full_cmd], cwd=str(REPO_ROOT), creationflags=subprocess.CREATE_NEW_CONSOLE)
    except OSError as exc:
        return LaunchResult(launched=False, detail=f"Couldn't open a terminal: {exc}", notify=True)

    if mcp_ok:
        return LaunchResult(launched=True, detail=mcp_detail, notify=False)
    return LaunchResult(launched=True, detail=f"Terminal aberto, mas: {mcp_detail}", notify=True)


@router.post("/claude-desktop", response_model=LaunchResult)
def launch_claude_desktop():
    """Uncertain by nature — there's no single known install path/URI scheme for
    Claude Desktop across machines. Set AUTOMATION_CLAUDE_DESKTOP_CMD to whatever
    actually launches it on this machine (e.g. the full path to Claude.exe, or a
    registered claude:// URI) if the default guess below doesn't work."""
    cmd = os.environ.get("AUTOMATION_CLAUDE_DESKTOP_CMD")
    if not cmd:
        return LaunchResult(
            launched=False,
            notify=True,
            detail=(
                "AUTOMATION_CLAUDE_DESKTOP_CMD nao configurado — defina essa variavel de "
                "ambiente com o comando/caminho que abre o Claude Desktop nesta maquina "
                "(ex: o caminho completo do Claude.exe) e reinicie o backend."
            ),
        )
    try:
        # os.startfile is the dedicated Windows API for "open this the way double-
        # clicking it in Explorer would" (a .exe path, a URL, or a registered
        # protocol like claude://) — avoids cmd.exe/start's quoting quirks entirely.
        os.startfile(cmd)  # type: ignore[attr-defined]
    except OSError as exc:
        return LaunchResult(launched=False, detail=f"Couldn't launch Claude Desktop: {exc}", notify=True)
    return LaunchResult(launched=True, notify=False)
