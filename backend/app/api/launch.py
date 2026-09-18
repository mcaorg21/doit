"""Editor shortcut buttons ("Abrir Terminal" / "Abrir Claude Desktop") that launch a
local app on THIS machine — the one running the backend. Only makes sense today,
while the backend runs on the same machine as the person clicking the button: once
this app moves to a shared server (see docs/mcp-connector.md), these endpoints would
launch a process on the SERVER, not the caller's machine, and since the rest of this
API has no authentication, anyone on the network could trigger them. Revisit (add
auth, or drop this feature) before that move — this is a deliberate, accepted
trade-off for now, not an oversight.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from typing import Literal

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

CliProvider = Literal["claude", "codex"]


def _resolve_cli(name: str) -> str:
    """`subprocess.run(["codex", ...])` (no shell=True) calls CreateProcess directly,
    which — unlike cmd.exe — does NOT apply PATHEXT extension resolution. `claude` on
    this machine happens to be a real .exe so this never bit it, but `codex` (npm-
    installed) is a `codex.cmd` shim and silently failed with WinError 2 ("cannot
    find the file") until resolved explicitly. shutil.which does the same PATHEXT-
    aware search a normal shell would. Falls back to the bare name (so the resulting
    error at least names the real command that couldn't be found) if not found."""
    return shutil.which(name) or name


class LaunchTerminalRequest(BaseModel):
    provider: CliProvider = "claude"
    projectId: str | None = None
    workflowId: str | None = None
    instruction: str | None = None
    """Free-form text (typically voice-dictated in the editor) to use as the CLI's
    starting instruction instead of the generic "continue editing" prompt — see
    _initial_prompt. Unlike projectId/workflowId, this is NOT restricted to
    _SAFE_ID_RE since it's arbitrary human language; see _sanitize_for_batch_arg for
    how it's made safe to embed in the generated .bat."""
    language: Literal["en", "pt"] | None = None
    """The editor's current UI language (see frontend/src/i18n/), passed through so
    the agent writes node titles/notes in the same language the human is looking at
    the app in — see _initial_prompt."""


class LaunchResult(BaseModel):
    launched: bool
    detail: str | None = None
    notify: bool = False
    """Whether the frontend should actually show `detail` to the user — false for a
    routine, nothing-to-report success (e.g. the MCP server was already registered),
    so a normal click doesn't pop a modal just to say "everything's fine"."""


def _ensure_claude_mcp_registered() -> tuple[bool, str]:
    try:
        listed = subprocess.run(
            [_resolve_cli("claude"), "mcp", "list"], capture_output=True, text=True, timeout=15, cwd=str(REPO_ROOT)
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Couldn't check registered MCP servers ({exc}) — is 'claude' on PATH?"

    if any(line.strip().startswith(f"{_MCP_SERVER_NAME}:") for line in listed.stdout.splitlines()):
        return True, "MCP server already registered"

    try:
        added = subprocess.run(
            [_resolve_cli("claude"), "mcp", "add", "--transport", "http", _MCP_SERVER_NAME, _MCP_URL],
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


def _ensure_codex_mcp_registered() -> tuple[bool, str]:
    """Same idea as _ensure_claude_mcp_registered, but for the Codex CLI (`codex mcp
    ...`, confirmed via `codex mcp add --help` — it uses --url for a streamable HTTP
    server, same protocol/endpoint this app already serves for Claude, and `codex mcp
    list --json` returns a JSON array of {"name": ...} objects rather than the
    human-formatted lines `claude mcp list` prints)."""
    try:
        listed = subprocess.run(
            [_resolve_cli("codex"), "mcp", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(REPO_ROOT),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Couldn't check registered MCP servers ({exc}) — is 'codex' on PATH?"

    try:
        servers = json.loads(listed.stdout) if listed.stdout.strip() else []
    except json.JSONDecodeError:
        servers = []
    if any(isinstance(s, dict) and s.get("name") == _MCP_SERVER_NAME for s in servers):
        return True, "MCP server already registered"

    try:
        added = subprocess.run(
            [_resolve_cli("codex"), "mcp", "add", _MCP_SERVER_NAME, "--url", _MCP_URL],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(REPO_ROOT),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Couldn't register the MCP server: {exc}"

    if added.returncode != 0:
        return False, (added.stderr or added.stdout).strip() or "codex mcp add failed"
    return True, "MCP server registered"


def _ensure_mcp_registered(provider: CliProvider) -> tuple[bool, str]:
    """Best-effort: any failure here still lets the terminal open, just with a
    warning in the response."""
    if provider == "codex":
        return _ensure_codex_mcp_registered()
    return _ensure_claude_mcp_registered()


def _validate_id(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    if not _SAFE_ID_RE.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid {label}")
    return value


def _initial_prompt(
    project_id: str | None, workflow_id: str | None, instruction: str | None = None, language: str | None = None
) -> str | None:
    if not (project_id and workflow_id):
        return None
    parts = [
        f"Continue editando o workflow (project_id={project_id}, workflow_id={workflow_id}) "
        f"no app auto-mation via o MCP '{_MCP_SERVER_NAME}' ({_MCP_URL}). SEMPRE comece chamando "
        f"get_workflow — isso retorna os nodes/edges ja existentes e o campo `notes`. Se `notes` ja "
        f"tiver conteudo, ou ja existirem nodes no workflow, uma sessao anterior ja avancou nele: "
        f"CONTINUE a partir do que ja esta la, nao recrie o workflow do zero. So comece do zero se o "
        f"workflow estiver genuinamente vazio (sem nodes e sem notes)."
    ]
    parts.append(
        f"Tambem chame list_workflow_notes(project_id={project_id!r}) pra ver o que ja foi aprendido/"
        "documentado em OUTROS workflows deste MESMO projeto (login parecido, seletores, particularidades "
        "de dados, etc). Se algo la for relevante pro que voce vai construir/editar aqui, reaproveite em vez "
        "de redescobrir do zero — e diga explicitamente no seu resumo final de qual(is) workflow(s) voce "
        "aproveitou algo, citando o nome dele(s)."
    )
    if language == "en":
        parts.append(
            "The editor's UI language is currently set to English — when you set a custom `title` or `note` "
            "on a node (add_node/update_node), write it in English."
        )
    else:
        parts.append(
            "O idioma da interface do editor esta em portugues — ao definir um `title` ou `note` customizado "
            "num node (add_node/update_node), escreva em portugues."
        )
    instruction = (instruction or "").strip()
    if instruction:
        parts.append(
            f'O usuario ditou por voz a seguinte instrucao: "{instruction}" — trate isso como o proximo '
            f"passo a partir do estado atual do workflow (visto em get_workflow), nao como uma "
            f"especificacao completa pra reconstruir tudo do zero."
        )
        parts.append(
            "Esta e uma sessao guiada por voz: depois de cada passo concluido, ou antes de decidir "
            "sozinho o que fazer a seguir, chame a tool ask_human_voice perguntando algo curto tipo "
            "'E agora?' e espere a resposta antes de continuar. Repita isso ate a pessoa sinalizar que "
            "terminou."
        )
    parts.append(
        f"Quando terminar essa sessao de construcao, chame a tool write_workflow_notes "
        f"(project_id={project_id}, workflow_id={workflow_id}) com um resumo conciso em markdown do "
        f'que voce construiu ou alterou — use mode="append" (o padrao), nunca substitua as notes '
        f"anteriores, pra sessao seguinte tambem saber o historico completo."
    )
    return "\n\n".join(parts)


def _sanitize_for_batch_arg(text: str) -> str:
    """Makes free-form dictated text safe to embed as a quoted argument inside the
    generated .bat (see _write_launch_script) — unlike project_id/workflow_id
    (_SAFE_ID_RE-restricted), this text is arbitrary human language. Collapses
    embedded newlines (would otherwise split the single command line), swaps "
    for ' (an unescaped " would end the quoted argument early), and doubles any %
    (cmd.exe treats %...% as variable expansion even inside double quotes — a
    dictated "100% dos casos" would otherwise silently vanish)."""
    return " ".join(text.split()).replace('"', "'").replace("%", "%%")


_PROVIDER_LABELS: dict[CliProvider, str] = {"claude": "Claude Code", "codex": "Codex"}


def _write_launch_script(provider: CliProvider, prompt: str | None) -> str:
    """Writes a one-off .bat to the temp dir that cd's into the repo and starts the
    CLI — see the comment in launch_terminal for why a real file (not a re-parsed
    shell string) is what makes embedding the prompt text safe. Left behind in TEMP
    after use, same as GENERATED_SCRIPTS_DIR's run scripts elsewhere in this app —
    small and harmless, not worth cleaning up."""
    cli_cmd = f'{provider} "{_sanitize_for_batch_arg(prompt)}"' if prompt else provider
    lines = [
        "@echo off",
        # Dictated instructions can contain accented PT-BR characters; without this,
        # cmd.exe's default console code page mangles them reading the UTF-8 .bat
        # file back. Never needed before — only ASCII alnum ids flowed through here.
        "chcp 65001 >nul",
        f"title {_PROVIDER_LABELS[provider]} - auto-mation",
        f'cd /d "{REPO_ROOT}"',
        cli_cmd,
    ]
    script_path = os.path.join(tempfile.gettempdir(), f"automation_launch_{uuid.uuid4().hex[:8]}.bat")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines) + "\r\n")
    return script_path


@router.post("/terminal", response_model=LaunchResult)
def launch_terminal(payload: LaunchTerminalRequest):
    project_id = _validate_id(payload.projectId, "projectId")
    workflow_id = _validate_id(payload.workflowId, "workflowId")
    provider = payload.provider

    mcp_ok, mcp_detail = _ensure_mcp_registered(provider)

    prompt = _initial_prompt(project_id, workflow_id, payload.instruction, payload.language)
    try:
        script_path = _write_launch_script(provider, prompt)
        # os.startfile (ShellExecute) opens the .bat the same way double-clicking it
        # would — a fresh console window, cmd.exe as the interpreter (required for
        # .bat/.cmd; they aren't directly executable via CreateProcess), and the
        # window stays open for as long as the last line (claude/codex itself, a
        # long-running interactive program) keeps running. This replaced an earlier
        # `cmd /k "title ... & claude \"...\""` approach that looked reasonable but
        # broke in practice: Python's list2cmdline quotes a Popen argv list using
        # normal C-runtime rules, but cmd.exe's own re-parsing of a /k or /c command
        # line does NOT follow those same rules, so the prompt's embedded quotes got
        # corrupted crossing that boundary (confirmed — it split the sentence on
        # whitespace instead of treating it as one argument). Writing a real .bat
        # FILE sidesteps this entirely: the prompt text only ever exists as plain
        # file content I write myself, never as something re-parsed through a shell
        # command-line twice.
        os.startfile(script_path)  # type: ignore[attr-defined]
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
