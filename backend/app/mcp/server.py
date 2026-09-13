"""MCP server exposing this app's own workflow builder as tools for an external LLM
(Claude Desktop/Code) — see the plan doc for the full design rationale. Two layers:

- Authoring (always available): create/edit nodes and connections in a workflow's
  JSON, no execution. Reuses the same storage functions the REST API uses
  (app/storage/workflow_store.py etc.) and the same repair/validation helpers the
  LLM-import feature already established (app/services/workflow_reconstructor.py).
- Live execution (app/mcp/live_sessions.py): opens a real, visible Playwright
  browser paused via pdb, and lets a "simple" node type (no nested block) be
  demonstrated for real before it's recorded — see live_sessions.py's module
  docstring for exactly how success/failure is detected.

Every mutating tool publishes to app/execution/workflow_events.py so an open editor
tab (see /ws/workflows/{id} in app/api/workflows.py) redraws live.
"""

import asyncio
import time
from typing import Any

from fastapi import HTTPException
from mcp.server.fastmcp import FastMCP

from app.codegen.context import CodegenError
from app.codegen.engine import generate_script
from app.execution import workflow_events
from app.execution.runner import NODE_ERROR_MARKER, start_run, stop_run
from app.execution.triggers import _find_pause_points, find_root_node
from app.mcp import live_sessions, voice_prompts
from app.models.mcp import (
    AddNodeResult,
    ConnectNodesResult,
    DemoNodeResult,
    DeleteNodeResult,
    FinishLiveSessionResult,
    LiveSessionResult,
    NodeCatalogResponse,
    PauseForHumanResult,
    RunWorkflowResult,
    ValidateWorkflowResult,
    WorkflowSummary,
    WorkflowWithNotes,
    WriteWorkflowNotesResult,
)
from app.models.run import RunStatus
from app.models.workflow import Position, WFEdge, WFNode, Workflow, WorkflowCreate, WorkflowSave
from app.nodes.registry import NODE_REGISTRY
from app.services.workflow_reconstructor import (
    LAYOUT_STEP_X,
    LAYOUT_Y,
    STRUCTURAL_RULES,
    build_node_catalog,
    downgrade_node_if_missing_credential,
)
from app.storage import folder_store, project_store, workflow_store
from app.storage.ids import gen_id

NODE_START_MARKER = "__NODE_START__"
NODE_PAUSED_MARKER = "__NODE_PAUSED__"
DEFAULT_RUN_TIMEOUT_SECONDS = 120.0

mcp = FastMCP(
    "auto-mation",
    # Mounted at /mcp in app/main.py — without this, FastMCP's own default internal
    # route ("/mcp") would double up with the mount prefix, landing the real
    # endpoint at /mcp/mcp instead of /mcp (confirmed by testing the mounted app
    # directly, not assumed from docs).
    streamable_http_path="/",
    instructions=(
        "Build browser-automation workflows in this local app using only its own "
        "registered node types. Call get_node_catalog() first. Prefer "
        "start_live_session + demo_node for straight-line sequences of simple steps "
        "(navigate/fill/click/...) so the human watches it happen for real; fall back "
        "to add_node/connect_nodes for anything demo_node rejects (loops, "
        "conditionals, or when there's no live session). Never invent a node type — "
        "if a step genuinely needs one that doesn't exist yet, STOP and ask the human "
        "whether they want a new node type built for it (this is a normal, expected "
        "request in this project — new node types get added directly to the "
        "backend's own source, which you can't do through this MCP server) before "
        "falling back to type=\"unknown\" with a clear params.code/sourceHint as a "
        "last resort. Either way, tell the human it needs attention rather than "
        "silently chaining more steps on top of an 'unknown' placeholder. Stuck "
        "mid-build inside a LIVE SESSION specifically (demo_node keeps failing on "
        "the same step, a custom widget you can't identify from the DOM) — call "
        "pause_for_human instead of giving up quietly or closing the session: it "
        "records a Pause node right where you stopped and leaves the live browser "
        "open and paused exactly as it is, so the human can inspect the real page "
        "themselves (it's visibly open on their screen unless headless=True) "
        "instead of guessing blind. Never call finish_live_session just because "
        "you're stuck. To check "
        "an existing workflow still works — after editing it, or as a maintenance "
        "pass — call run_workflow: it runs the whole thing for real and tells you "
        "exactly which node broke, if any. Working on an EXISTING workflow (editing "
        "it further, running it, debugging a failure)? Call get_workflow first and "
        "read its `notes` field before doing anything else — that's where a human "
        "writes down what this specific workflow does, known quirks, and how to "
        "validate/run it; it exists specifically to help you. In a VOICE-GUIDED "
        "session (the human dictated your starting instruction instead of typing "
        "it): after each step you finish, or whenever you're not sure what to do "
        "next, call ask_human_voice with a short question like \"E agora?\" and wait "
        "for the answer instead of guessing — repeat this until the human signals "
        "they're done. When you finish a build/edit session — voice-guided or not — "
        "call write_workflow_notes with a concise markdown summary of what you did, "
        "so the notes stay useful for whoever (or whatever) works on this workflow "
        "next."
    ),
)

_MCP_NOTES = [
    "If a step in what the human is asking for needs a node type that isn't in "
    "get_node_catalog(), don't just downgrade to type=\"unknown\" and keep going — "
    "stop and ask the human whether they want a new node type built for that "
    "capability first. Adding a node type is normal, expected work in this project "
    "(it's a small, well-established pattern in the backend's own source — codegen "
    "function + NodeSpec registration + a frontend icon), just not something this "
    "MCP server's tools can do themselves. Only fall back to type=\"unknown\" once "
    "the human has declined or a new node isn't worth it for a one-off step.",
    "credentialId-type fields (see credentialType on a param in the catalog) cannot "
    "be filled by you — there is no credential-listing tool. If a step genuinely "
    "needs one of these node types (two_captcha, browser_2captcha, login, microsoft_login, totp), "
    "add_node will automatically turn it into an 'unknown' placeholder with a note "
    "instead of failing; check needsHumanAttention on the result rather than trying "
    "to work around it yourself. login specifically also can't be demoed live at all "
    "(see the next note) — always author it with add_node, then tell the human to "
    "pick its credential in the editor before the workflow can actually run.",
    "start_live_session/demo_node execute a step for real only while you're actively "
    "building it, one step at a time — for an already-saved workflow, run_workflow "
    "runs the WHOLE thing end to end unattended and reports whether it still works, "
    "which node broke if not, and the tail of its log. Use it after editing an "
    "existing workflow (e.g. adding a new node type) to prove the change actually "
    "works, or to health-check a workflow before it would fail for real on its own "
    "schedule/webhook. It's rejected up front if the workflow can reach a Pause node "
    "or a breakpointed connector — nothing unattended can click Continue past one of "
    "those, run it manually from the editor instead.",
    "loop, if, and browser_2captcha nodes can't be demonstrated live (they open a "
    "nested block) — author them with add_node/connect_nodes instead of demo_node. "
    "Save Files, Get File, Load Cookies, Login, and Microsoft Login can't either, same reason (their "
    "fragments contain indented blocks even though they don't open one at the graph "
    "level) — Login is rejected explicitly for the credential reason above too. "
    "download_file and save_cookies CAN be demonstrated live — download_file "
    "clicks a real element and waits for the real download; save_cookies just reads "
    "the live browser context's current cookies, both only recording the node once "
    "the real action actually succeeded.",
]


def _get_workflow(project_id: str, workflow_id: str) -> Workflow:
    try:
        return workflow_store.get_workflow(project_id, workflow_id)
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc


def _save(project_id: str, workflow_id: str, workflow: Workflow) -> Workflow:
    return workflow_store.save_workflow(
        project_id,
        workflow_id,
        WorkflowSave(name=workflow.name, nodes=workflow.nodes, edges=workflow.edges, startNodeId=workflow.startNodeId),
    )


def _clean_params(node_type: str, params: dict[str, Any] | None, catalog: list[dict]) -> dict[str, Any]:
    schema_by_type = {s["type"]: s for s in catalog}
    spec_dict = schema_by_type.get(node_type)
    if spec_dict is None:
        raise ValueError(f"Unknown node type '{node_type}' — call get_node_catalog() first")
    allowed_keys = {p["key"] for p in spec_dict["params"]}
    return {k: v for k, v in (params or {}).items() if k in allowed_keys}


def _validate_new_edge(workflow: Workflow, source: str, target: str, source_handle: str | None) -> None:
    node_map = {n.id: n for n in workflow.nodes}
    if source not in node_map:
        raise ValueError(f"Source node '{source}' not found in this workflow")
    if target not in node_map:
        raise ValueError(f"Target node '{target}' not found in this workflow")
    spec = NODE_REGISTRY.get(node_map[source].type)
    if spec is None:
        raise ValueError(f"Source node '{source}' has an unrecognized type '{node_map[source].type}'")

    outgoing_from_source = [e for e in workflow.edges if e.source == source]
    if spec.is_branch:
        if source_handle not in ("true", "false"):
            raise ValueError(f"'{node_map[source].type}' is a branching node — source_handle must be \"true\" or \"false\"")
        if any(e.sourceHandle == source_handle for e in outgoing_from_source):
            raise ValueError(f"Source node '{source}' already has a connection from its '{source_handle}' output")
    else:
        if outgoing_from_source:
            raise ValueError(f"Source node '{source}' already has an outgoing connection — this node type can't branch")
        if source_handle is not None:
            raise ValueError(f"Source node '{source}' isn't a branching node — omit source_handle")

    if any(e.target == target for e in workflow.edges):
        raise ValueError(f"Target node '{target}' already has an incoming connection — merging isn't supported")


# ---------------------------------------------------------------------------
# Layer 1 — authoring
# ---------------------------------------------------------------------------


@mcp.tool()
def get_node_catalog() -> NodeCatalogResponse:
    """Call this first. Returns every node type this app supports, its exact param
    schema, and the structural rules a workflow graph must follow (single root,
    branch-handle rules, no cycles, when to use "unknown", etc.)."""
    return NodeCatalogResponse(nodeTypes=build_node_catalog(), structuralRules=STRUCTURAL_RULES, notes=_MCP_NOTES)


@mcp.tool()
def list_projects() -> list[dict]:
    """Lists existing projects (id, name, timestamps). There is no create_project
    tool — if no suitable project exists, ask the human to create one in the UI."""
    return [p.model_dump(mode="json") for p in project_store.list_projects()]


@mcp.tool()
def list_folders(project_id: str) -> list[dict]:
    """Lists a project's folders, so create_workflow's folder_id can place the new
    workflow somewhere other than the project root."""
    try:
        return [f.model_dump(mode="json") for f in folder_store.list_folders(project_id)]
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc


@mcp.tool()
def list_workflows(project_id: str) -> list[dict]:
    """Lists a project's workflows (id, name, published state, timestamps) — use to
    find an existing workflow's id, e.g. when the human asks to keep editing
    something built in an earlier conversation."""
    try:
        return [w.model_dump(mode="json") for w in workflow_store.list_workflows(project_id)]
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc


@mcp.tool()
def get_workflow(project_id: str, workflow_id: str) -> WorkflowWithNotes:
    """Returns a workflow's current nodes and edges, plus its `notes` field — call
    this before editing an existing workflow further (e.g. in a new conversation, or
    before run_workflow/demo_node) so you know what's already there instead of
    guessing. ALWAYS read `notes` first if it's non-empty: it's human-written
    guidance for THIS specific workflow (what it does, known quirks, what to check
    if it breaks, how to run/validate it) — written via the "Notes" button next to
    the AI launch button in the editor topbar, meant specifically to help you work
    on this workflow correctly."""
    workflow = _get_workflow(project_id, workflow_id)
    notes = workflow_store.get_workflow_notes(project_id, workflow_id)
    return WorkflowWithNotes(**workflow.model_dump(), notes=notes)


@mcp.tool()
def create_workflow(project_id: str, name: str, folder_id: str | None = None) -> WorkflowSummary:
    """Creates an empty, unpublished workflow — the starting point before any
    add_node/start_live_session call. Tell the human to open its editor URL now if
    they want to watch it get built live."""
    try:
        workflow = workflow_store.create_workflow(project_id, WorkflowCreate(name=name, folderId=folder_id))
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc
    return WorkflowSummary(workflowId=workflow.id, projectId=project_id, name=workflow.name)


@mcp.tool()
async def add_node(
    project_id: str,
    workflow_id: str,
    type: str,
    params: dict[str, Any] | None = None,
    title: str | None = None,
    note: str | None = None,
) -> AddNodeResult:
    """Adds one node, auto-positioned after the current last node — pure authoring,
    nothing is executed. Use ONLY types from get_node_catalog(); never invent a type.
    If a step genuinely needs a node type that doesn't exist, don't reach for
    type="unknown" as your first move — STOP and ask the human whether they want a
    new node type built for it first (normal in this project; it's a source change
    on the backend, not something this tool can do). Only use type="unknown" with
    params={"code": "...", "sourceHint": "..."} as the fallback once that's been
    asked/declined. If the result's needsHumanAttention is true (type ended up
    "unknown", possibly because it needed a credential this server can't provide),
    stop chaining further steps that depend on this node's output and tell the human
    it needs manual setup in the editor."""
    workflow = _get_workflow(project_id, workflow_id)
    catalog = build_node_catalog()
    clean_params = _clean_params(type, params, catalog)

    new_node = WFNode(
        id=gen_id("node"),
        type=type,
        position=Position(x=LAYOUT_STEP_X * len(workflow.nodes), y=LAYOUT_Y),
        params=clean_params,
        title=title,
        note=note,
    )
    downgrade_note = downgrade_node_if_missing_credential(new_node, catalog)

    workflow.nodes.append(new_node)
    _save(project_id, workflow_id, workflow)
    workflow_events.publish(workflow_id, {"type": "node_added", "node": new_node.model_dump(mode="json")})

    return AddNodeResult(
        node=new_node, downgraded=downgrade_note is not None, note=downgrade_note, needsHumanAttention=(new_node.type == "unknown")
    )


@mcp.tool()
async def connect_nodes(
    project_id: str, workflow_id: str, source: str, target: str, source_handle: str | None = None
) -> ConnectNodesResult:
    """Connects source -> target. Mirrors this app's own structural rules exactly, so
    a bad edge is rejected here rather than silently saved: a branching node (e.g.
    "if") needs source_handle "true" or "false" and can't reuse the same handle
    twice; any other node can have at most one outgoing edge; no node may have more
    than one incoming edge (branches never rejoin)."""
    workflow = _get_workflow(project_id, workflow_id)
    _validate_new_edge(workflow, source, target, source_handle)

    new_edge = WFEdge(id=gen_id("edge"), source=source, target=target, sourceHandle=source_handle)
    workflow.edges.append(new_edge)
    _save(project_id, workflow_id, workflow)
    workflow_events.publish(workflow_id, {"type": "edge_added", "edge": new_edge.model_dump(mode="json")})
    return ConnectNodesResult(edge=new_edge)


@mcp.tool()
async def update_node(
    project_id: str,
    workflow_id: str,
    node_id: str,
    params: dict[str, Any] | None = None,
    title: str | None = None,
    note: str | None = None,
) -> WFNode:
    """Merges `params` into the node's existing params (does not replace them
    wholesale) and/or updates title/note."""
    workflow = _get_workflow(project_id, workflow_id)
    node = next((n for n in workflow.nodes if n.id == node_id), None)
    if node is None:
        raise ValueError(f"Node '{node_id}' not found in this workflow")

    if params:
        catalog = build_node_catalog()
        clean = _clean_params(node.type, {**node.params, **params}, catalog)
        node.params = clean
    if title is not None:
        node.title = title
    if note is not None:
        node.note = note

    _save(project_id, workflow_id, workflow)
    workflow_events.publish(workflow_id, {"type": "node_updated", "node": node.model_dump(mode="json")})
    return node


@mcp.tool()
async def delete_node(project_id: str, workflow_id: str, node_id: str) -> DeleteNodeResult:
    """Removes a node and any edges touching it."""
    workflow = _get_workflow(project_id, workflow_id)
    if not any(n.id == node_id for n in workflow.nodes):
        raise ValueError(f"Node '{node_id}' not found in this workflow")

    removed_edge_ids = [e.id for e in workflow.edges if e.source == node_id or e.target == node_id]
    workflow.nodes = [n for n in workflow.nodes if n.id != node_id]
    workflow.edges = [e for e in workflow.edges if e.id not in removed_edge_ids]
    _save(project_id, workflow_id, workflow)

    workflow_events.publish(workflow_id, {"type": "node_removed", "nodeId": node_id})
    for edge_id in removed_edge_ids:
        workflow_events.publish(workflow_id, {"type": "edge_removed", "edgeId": edge_id})
    return DeleteNodeResult(deletedNodeId=node_id, deletedEdgeIds=removed_edge_ids)


@mcp.tool()
def validate_workflow(project_id: str, workflow_id: str) -> ValidateWorkflowResult:
    """Runs the full structural check (single root, branch-handle rules, no cycles,
    per-node required-field checks) on demand — call this once near the end of a
    build, not after every add_node/connect_nodes (a graph is normally transiently
    "incomplete" mid-build). Never persists anything."""
    workflow = _get_workflow(project_id, workflow_id)
    try:
        generate_script(
            workflow.nodes, workflow.edges, project_id, start_node_id=workflow.startNodeId, workflow_id=workflow_id
        )
    except CodegenError as exc:
        return ValidateWorkflowResult(ok=False, error=str(exc))
    return ValidateWorkflowResult(ok=True)


@mcp.tool()
async def run_workflow(
    project_id: str, workflow_id: str, timeout_seconds: float = DEFAULT_RUN_TIMEOUT_SECONDS
) -> RunWorkflowResult:
    """Actually RUNS an existing, already-saved workflow end to end for real (same as
    clicking Run in the editor) with whatever settings it already has (headless,
    browser channel, ...) and waits for it to finish. Use this to confirm a workflow
    still works after you've changed it (e.g. added a new node type, edited a
    selector) — validate_workflow only proves the graph compiles, not that it
    actually runs — or as a maintenance health-check across several workflows to see
    which ones need fixing before they'd fail for real on their own schedule/webhook.
    Rejected up front (a ValueError, nothing started) if the workflow can reach a
    Pause node or a breakpointed connector, since nothing here can ever click
    Continue past one — those have to be run manually from the editor instead. Waits
    up to timeout_seconds; past that the run is stopped and reported as "timedOut"
    rather than left running forever. On failure, failedNodeId/failedNodeLabel/
    errorMessage say exactly what needs fixing; logTail has the run's last lines for
    more context."""
    workflow = _get_workflow(project_id, workflow_id)
    root = find_root_node(workflow.nodes, workflow.edges, workflow.startNodeId)
    if root is not None:
        pause_points = _find_pause_points(workflow.nodes, workflow.edges, root)
        if pause_points:
            names = "; ".join(pause_points)
            raise ValueError(
                f"Can't run unattended — this workflow can reach: {names}. Nothing here can click Continue "
                "past a breakpoint; remove it first, or run this workflow manually from the editor instead."
            )

    try:
        script = generate_script(
            workflow.nodes, workflow.edges, project_id, start_node_id=workflow.startNodeId, workflow_id=workflow_id
        )
    except CodegenError as exc:
        raise ValueError(str(exc)) from exc

    node_label_by_id = {n.id: (n.title or n.id) for n in workflow.nodes}
    # unattended=False (the default) is deliberate: an agent is actively watching this
    # call and will report the result back to a human, same as a manual Run-button
    # click — unlike a real schedule/webhook fire, a failure here must NOT auto-
    # unpublish the workflow (see app/execution/runner.py's _stream_output).
    handle = await start_run(project_id, workflow_id, script)

    log_tail: list[str] = []
    failed_node_id: str | None = None
    error_message: str | None = None
    timed_out = False
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            await stop_run(handle)
            break
        try:
            line = await asyncio.wait_for(handle.queue.get(), timeout=remaining)
        except asyncio.TimeoutError:
            timed_out = True
            await stop_run(handle)
            break
        if line is None:
            break
        text = line.text
        if text.startswith(NODE_ERROR_MARKER):
            failed_node_id = text[len(NODE_ERROR_MARKER) :].strip()
            continue
        if text.startswith(NODE_START_MARKER) or text.startswith(NODE_PAUSED_MARKER):
            continue
        log_tail.append(text)
        if failed_node_id is not None and error_message is None and text.startswith("Tratar erro no node"):
            error_message = text
            # The engine's auto-wrap calls breakpoint() right after printing this line
            # (see engine.py's render()) — the script is about to hang at pdb forever,
            # since nothing unattended can ever send it "continue". No point waiting
            # out the rest of timeout_seconds to learn that; stop it now and report
            # what actually broke, immediately.
            await stop_run(handle)
            break

    if failed_node_id is not None:
        status = "error"
    elif timed_out:
        status = "timedOut"
    elif handle.record.status == RunStatus.cancelled:
        status = "cancelled"
    elif handle.record.status == RunStatus.success:
        status = "success"
    else:
        status = "error"

    return RunWorkflowResult(
        ok=status == "success",
        status=status,
        runId=handle.run_id,
        failedNodeId=failed_node_id,
        failedNodeLabel=node_label_by_id.get(failed_node_id) if failed_node_id else None,
        errorMessage=error_message,
        logTail=log_tail[-20:],
    )


# ---------------------------------------------------------------------------
# Layer 2 — live execution
# ---------------------------------------------------------------------------


@mcp.tool()
async def start_live_session(
    project_id: str, workflow_id: str, headless: bool = False, browser_channel: str = "chrome"
) -> LiveSessionResult:
    """Opens a REAL browser (visible unless headless=True) paused and ready for
    demo_node calls, and records the matching open_browser node for real. Only one
    live session per workflow at a time. Call finish_live_session when you're done
    (or about to stop responding for a while) so the browser doesn't stay open
    unattended."""
    workflow = _get_workflow(project_id, workflow_id)
    try:
        session = await live_sessions.start_session(project_id, workflow_id, headless, browser_channel)
    except live_sessions.LiveSessionError as exc:
        raise ValueError(str(exc)) from exc

    new_node = WFNode(
        id=gen_id("node"),
        type="open_browser",
        position=Position(x=LAYOUT_STEP_X * len(workflow.nodes), y=LAYOUT_Y),
        params={"headless": headless, "browserChannel": browser_channel},
    )
    workflow.nodes.append(new_node)
    _save(project_id, workflow_id, workflow)
    workflow_events.publish(workflow_id, {"type": "node_added", "node": new_node.model_dump(mode="json")})
    session.last_node_id = new_node.id

    return LiveSessionResult(workflowId=workflow_id, openBrowserNode=new_node)


@mcp.tool()
async def demo_node(
    project_id: str,
    workflow_id: str,
    type: str,
    params: dict[str, Any] | None = None,
    title: str | None = None,
    note: str | None = None,
) -> DemoNodeResult:
    """Runs one step FOR REAL against the live session's browser (goto/fill/click/
    hover/select_option/wait/element_present/get_text/execute_script/html_list_select/
    http_request-without-autoLoop/download_file/save_cookies only — loop/if/
    browser_2captcha aren't demoable, use add_node instead; Save Files/Get File/Load
    Cookies/Login aren't demoable either, same reason — use add_node for those too
    (Login also always needs a credential this server can't supply, so it'll come
    back as an 'unknown' placeholder either way). execute_script is exactly
    Selenium/ChromeDriver's execute_script(): raw JS, arguments[0]/arguments[1]/...
    for whatever you pass in `args`, `return` becomes the result — useful for
    anything no other node covers (reading a computed style, dispatching a custom
    event, scrolling, ...). For download_file specifically: the node is only recorded once
    the download actually finishes and the file is saved successfully — a timeout or
    a click that never triggers a download fails the step like any other, nothing is
    persisted, and capturedOutput reports the saved filename/path only, never
    cookies/tokens/headers. Only records the node and connects it after the
    session's last node if the step actually succeeds; on failure nothing is
    persisted and capturedOutput has what went wrong — adjust params and call
    demo_node again (that's how you self-correct; there's no retry limit enforced
    here, use your own judgment about when to stop and ask the human instead)."""
    session = live_sessions.get_session(workflow_id)
    if session is None:
        raise ValueError("No live session for this workflow — call start_live_session first, or use add_node to author without demoing")

    demoable, reason = live_sessions.is_demoable(type)
    if not demoable:
        raise ValueError(reason or f"'{type}' can't be demoed live — use add_node instead")

    catalog = build_node_catalog()
    clean_params = _clean_params(type, params, catalog)
    node_label = title or type

    try:
        ok, captured, ctx = await live_sessions.run_demo_step(session, type, clean_params, node_label)
    except live_sessions.LiveSessionError as exc:
        raise ValueError(str(exc)) from exc

    if not ok:
        return DemoNodeResult(node=None, edge=None, ok=False, downgraded=False, capturedOutput=captured)

    workflow = _get_workflow(project_id, workflow_id)
    new_node = WFNode(
        id=gen_id("node"),
        type=type,
        position=Position(x=LAYOUT_STEP_X * len(workflow.nodes), y=LAYOUT_Y),
        params=clean_params,
        title=title,
        note=note,
    )
    downgrade_note = downgrade_node_if_missing_credential(new_node, catalog)
    workflow.nodes.append(new_node)

    new_edge: WFEdge | None = None
    if session.last_node_id is not None:
        new_edge = WFEdge(id=gen_id("edge"), source=session.last_node_id, target=new_node.id)
        workflow.edges.append(new_edge)

    _save(project_id, workflow_id, workflow)
    workflow_events.publish(workflow_id, {"type": "node_added", "node": new_node.model_dump(mode="json")})
    if new_edge is not None:
        workflow_events.publish(workflow_id, {"type": "edge_added", "edge": new_edge.model_dump(mode="json")})

    session.last_node_id = new_node.id
    spec = NODE_REGISTRY[type]
    if spec.browser_var_after:
        session.browser_var = spec.browser_var_after(ctx) or session.browser_var
    if spec.target_var_after:
        session.target_var = spec.target_var_after(ctx)

    return DemoNodeResult(
        node=new_node,
        edge=new_edge,
        ok=True,
        downgraded=downgrade_note is not None,
        note=downgrade_note,
        needsHumanAttention=(new_node.type == "unknown"),
        capturedOutput=captured,
    )


@mcp.tool()
async def pause_for_human(project_id: str, workflow_id: str, reason: str) -> PauseForHumanResult:
    """Call this the moment you're genuinely stuck mid-build and can't figure out the
    next step yourself — e.g. demo_node keeps failing on the same selector after a
    few honest attempts, or the page uses some custom widget (a combobox that isn't
    a real <select>, a canvas-drawn control, ...) you can't identify from the DOM
    alone. Records a Pause node (its note set to `reason`) right after the last
    successful step, so the saved workflow shows exactly where a human needs to
    step in — same as a human manually adding a breakpoint, and picked up by the
    same red-while-paused highlighting in the editor. Does NOT touch the live
    browser at all: it's already sitting right at this exact point (paused, and
    visibly open on the human's screen unless this session was started with
    headless=True) — that's the point of calling this instead of giving up
    silently. After calling this, tell the human clearly what you're stuck on and
    what you need from them (e.g. "open DevTools on the still-open browser window
    and send me the selector for X"), and do NOT call finish_live_session — leave
    the session open until they've helped you past this point or tell you to stop."""
    session = live_sessions.get_session(workflow_id)
    if session is None:
        raise ValueError(
            "No live session for this workflow — there's no live browser to leave open. If you're stuck while "
            "authoring with add_node (no live session), use type=\"unknown\" instead, per the usual rule."
        )

    workflow = _get_workflow(project_id, workflow_id)
    new_node = WFNode(
        id=gen_id("node"),
        type="pause",
        position=Position(x=LAYOUT_STEP_X * len(workflow.nodes), y=LAYOUT_Y),
        note=reason,
    )
    workflow.nodes.append(new_node)

    new_edge: WFEdge | None = None
    if session.last_node_id is not None:
        new_edge = WFEdge(id=gen_id("edge"), source=session.last_node_id, target=new_node.id)
        workflow.edges.append(new_edge)

    _save(project_id, workflow_id, workflow)
    workflow_events.publish(workflow_id, {"type": "node_added", "node": new_node.model_dump(mode="json")})
    if new_edge is not None:
        workflow_events.publish(workflow_id, {"type": "edge_added", "edge": new_edge.model_dump(mode="json")})

    session.last_node_id = new_node.id

    return PauseForHumanResult(
        node=new_node,
        edge=new_edge,
        message=(
            "Pause node recorded. The live browser is untouched — still open and paused exactly where you left "
            "it. Tell the human what you're stuck on now; don't call finish_live_session until they've resolved it."
        ),
    )


@mcp.tool()
async def ask_human_voice(project_id: str, workflow_id: str, question: str, timeout_seconds: float = 600) -> str:
    """Ask the human something and WAIT for their answer by voice, inside the app
    itself (not this terminal). Use this whenever you finish a step in a
    voice-guided session, or whenever you're not sure what to do next — ask
    something short like "E agora?" or "Finished X, what next?". The human sees a
    mic prompt in the browser tab where this workflow is open; their answer
    (transcribed and reviewed by them) becomes this call's return value. Raises an
    error if nobody answers within timeout_seconds — in that case, try again or ask
    directly in this terminal as a fallback."""
    _get_workflow(project_id, workflow_id)
    return await voice_prompts.ask(workflow_id, question, timeout_seconds)


@mcp.tool()
def write_workflow_notes(project_id: str, workflow_id: str, summary: str, mode: str = "append") -> WriteWorkflowNotesResult:
    """Write markdown into this workflow's Notes — the write counterpart to
    get_workflow's read-only `notes` field, and the same file the "Notes" button in
    the editor topbar edits. Call this when you finish a build/edit session
    (especially one kicked off from a dictated voice instruction) with a CONCISE
    markdown summary of what you built or changed — the next session reads `notes`
    first, so this is how it learns what happened here. mode="append" (default)
    adds `summary` after whatever notes already exist, separated by a horizontal
    rule, so a human's own prior guidance is never lost. mode="replace" OVERWRITES
    the whole file with just `summary` — only use this if the human explicitly
    asked you to rewrite the notes from scratch."""
    if mode not in ("append", "replace"):
        raise ValueError('mode must be "append" or "replace"')
    _get_workflow(project_id, workflow_id)
    summary = summary.strip()
    if mode == "append":
        existing = workflow_store.get_workflow_notes(project_id, workflow_id).rstrip()
        new_notes = f"{existing}\n\n---\n\n{summary}\n" if existing else f"{summary}\n"
    else:
        new_notes = f"{summary}\n"
    workflow_store.set_workflow_notes(project_id, workflow_id, new_notes)
    return WriteWorkflowNotesResult(notes=new_notes, mode=mode)


@mcp.tool()
async def finish_live_session(project_id: str, workflow_id: str) -> FinishLiveSessionResult:
    """Closes the live session's browser (best-effort graceful close, then force-
    stops the process either way) and frees it up for a new start_live_session
    call. Do NOT call this just because you're stuck — use pause_for_human instead,
    which leaves the browser open for the human to inspect. Only call this once the
    workflow is actually done, or the human explicitly says to stop/close it."""
    stopped = await live_sessions.finish_session(workflow_id)
    return FinishLiveSessionResult(workflowId=workflow_id, stopped=stopped)
