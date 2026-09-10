from pydantic import BaseModel, Field

from app.models.workflow import WFEdge, WFNode


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
