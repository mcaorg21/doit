from pydantic import BaseModel, Field

from app.models.workflow import WFEdge, WFNode, Workflow


class NodeCatalogResponse(BaseModel):
    """What get_node_catalog() returns — the MCP client's vocabulary for every other
    tool: which node `type` values exist and their exact param schema, plus the same
    structural rules text app/services/workflow_reconstructor.py already gives its own
    captive LLM, plus a few MCP-specific caveats (no credential tool, no live
    execution for block-opening node types)."""

    nodeTypes: list[dict]
    structuralRules: str
    notes: list[str] = Field(default_factory=list)


class WorkflowSummary(BaseModel):
    workflowId: str
    projectId: str
    name: str


class WorkflowWithNotes(Workflow):
    """get_workflow's MCP-specific return shape — the same Workflow fields the REST
    API uses, plus two sibling markdown docs neither part of Workflow itself (so the
    REST API's persisted JSON shape doesn't carry them around on every save):
    `notes` — the human-written INSTRUCTIONS for what this workflow should do (see
    the "Notes" button's "Instruções" tab in the editor topbar; app/storage/
    workflow_store.py::get_workflow_notes), and `experience` — the AI-accumulated
    build history, one summary per session (the "Experiência Adquirida" tab;
    ::get_workflow_experience), written via write_workflow_experience."""

    notes: str = ""
    experience: str = ""


class AddNodeResult(BaseModel):
    node: WFNode
    downgraded: bool
    note: str | None = None
    needsHumanAttention: bool
    """True whenever the persisted node ended up with type == "unknown" — whether
    because the caller asked for an unmapped step directly, or because add_node/
    demo_node downgraded it for a missing credential. The calling LLM should pause
    and flag this to the human rather than chaining further nodes that assume this
    one's output exists."""


class ConnectNodesResult(BaseModel):
    edge: WFEdge


class ValidateWorkflowResult(BaseModel):
    ok: bool
    error: str | None = None


class DeleteNodeResult(BaseModel):
    deletedNodeId: str
    deletedEdgeIds: list[str]


class LiveSessionResult(BaseModel):
    workflowId: str
    openBrowserNode: WFNode


class DemoNodeResult(BaseModel):
    node: WFNode | None
    """None when the step failed — nothing was persisted."""
    edge: WFEdge | None
    """The auto-created edge connecting this node after the session's previous node,
    or None on failure / when this is the session's very first demo_node call."""
    ok: bool
    downgraded: bool
    note: str | None = None
    needsHumanAttention: bool = False
    capturedOutput: list[str] = Field(default_factory=list)
    """Raw stdout/pdb lines captured while running this step — populated on failure
    (for the caller to see what actually went wrong) and best-effort on success."""


class FinishLiveSessionResult(BaseModel):
    workflowId: str
    stopped: bool


class PauseForHumanResult(BaseModel):
    node: WFNode
    """The Pause node just recorded, right after the live session's last successful
    step — its `note` holds the reason text passed to pause_for_human."""
    edge: WFEdge | None
    """Connects the previous step to this Pause node, or None if this was the
    session's very first step (nothing to connect from)."""
    message: str


class RunWorkflowResult(BaseModel):
    ok: bool
    """True only when the run finished with exit code 0 — the same bar a real
    scheduled/webhook fire would need to clear."""
    status: str
    """"success" | "error" | "cancelled" | "timedOut" — mirrors RunStatus, plus
    "timedOut" for when this tool gave up waiting (see timeoutSeconds) and stopped
    the run itself rather than leaving it running unattended."""
    runId: str
    failedNodeId: str | None = None
    failedNodeLabel: str | None = None
    """Set together — which node's own try/except caught an exception, identified by
    the __NODE_ERROR__ marker every generated script prints (see engine.py). This is
    "what needs fixing" for a maintenance pass."""
    errorMessage: str | None = None
    logTail: list[str] = Field(default_factory=list)
    """The run's last ~20 real log lines (internal __NODE_START__/__NODE_ERROR__/
    __NODE_PAUSED__ markers stripped out) — enough context to see what the workflow
    was doing right before it stopped, without dumping the whole run."""


class WriteWorkflowExperienceResult(BaseModel):
    experience: str
    """Full Experiência Adquirida contents after this write — same shape
    get_workflow's `experience` field returns."""
    mode: str
    """"append" or "replace", echoing back which one was actually used."""
