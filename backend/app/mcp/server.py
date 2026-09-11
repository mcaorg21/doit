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

from typing import Any

from fastapi import HTTPException
from mcp.server.fastmcp import FastMCP

from app.codegen.context import CodegenError
from app.codegen.engine import generate_script
from app.execution import workflow_events
from app.mcp import live_sessions
from app.models.mcp import (
    AddNodeResult,
    ConnectNodesResult,
    DemoNodeResult,
    DeleteNodeResult,
    FinishLiveSessionResult,
    LiveSessionResult,
    NodeCatalogResponse,
    ValidateWorkflowResult,
    WorkflowSummary,
)
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
        "use type=\"unknown\" with a clear params.code/sourceHint for anything that "
        "doesn't fit, and tell the human it needs manual attention rather than "
        "chaining more steps on top of it."
    ),
)

_MCP_NOTES = [
    "credentialId-type fields (see credentialType on a param in the catalog) cannot "
    "be filled by you — there is no credential-listing tool. If a step genuinely "
    "needs one of these node types (two_captcha, browser_2captcha), add_node/"
    "demo_node will automatically turn it into an 'unknown' placeholder with a note "
    "instead of failing; check needsHumanAttention on the result rather than trying "
    "to work around it yourself.",
    "This server never runs a finished workflow — running/scheduling stays a manual "
    "step in the editor. start_live_session/demo_node execute a step for real only "
    "while you're actively building it, one step at a time.",
    "loop, if, and browser_2captcha nodes can't be demonstrated live (they open a "
    "nested block) — author them with add_node/connect_nodes instead of demo_node. "
    "Save Files and Get File can't either, same reason (their fragments contain "
    "indented blocks even though they don't open one at the graph level). "
    "download_file CAN be demonstrated live — it clicks a real element, waits for "
    "the real download, and only records the node once the file is actually saved.",
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
def get_workflow(project_id: str, workflow_id: str) -> Workflow:
    """Returns a workflow's current nodes and edges — call this before editing an
    existing workflow further (e.g. in a new conversation) so you know what's
    already there instead of guessing."""
    return _get_workflow(project_id, workflow_id)


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
    nothing is executed. Use ONLY types from get_node_catalog(); use type="unknown"
    with params={"code": "...", "sourceHint": "..."} for any step with no matching
    node type — never invent a type. If the result's needsHumanAttention is true
    (type ended up "unknown", possibly because it needed a credential this server
    can't provide), stop chaining further steps that depend on this node's output and
    tell the human it needs manual setup in the editor."""
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
    hover/select_option/wait/get_text/element_present/http_request-without-autoLoop/
    download_file only — loop/if/browser_2captcha aren't demoable, use add_node
    instead; Save Files/Get File aren't demoable either, same reason — use add_node
    for those too). For download_file specifically: the node is only recorded once
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
async def finish_live_session(project_id: str, workflow_id: str) -> FinishLiveSessionResult:
    """Closes the live session's browser (best-effort graceful close, then force-
    stops the process either way) and frees it up for a new start_live_session
    call."""
    stopped = await live_sessions.finish_session(workflow_id)
    return FinishLiveSessionResult(workflowId=workflow_id, stopped=stopped)
