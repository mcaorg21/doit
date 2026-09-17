from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Position(BaseModel):
    x: float
    y: float


class WFNode(BaseModel):
    id: str
    type: str
    position: Position
    params: dict[str, Any] = Field(default_factory=dict)
    title: str | None = None
    """User-assigned display name shown on the node in the canvas, in place of the
    node type's default label — purely cosmetic, doesn't affect codegen."""
    note: str | None = None
    """Free-text explanation of what this node instance does — emitted as a comment
    above the node's code in the generated script."""
    fieldMap: list[str] | None = None
    """Dot-paths (e.g. "address.geo.lat") discovered from a Result preview and saved
    via the node's "Save Mapping" button — purely a frontend convenience so other
    fields' template picker can suggest them; doesn't affect codegen."""
    resultExamples: dict[str, Any] = Field(default_factory=dict)
    """Example value(s) this node's producesVariable param(s) actually held the last
    time it really ran — keyed by the param key (usually just "resultVar"; see
    app/codegen/engine.py's _result_capture_lines). Auto-captured and overwritten on
    every real Run (app/execution/runner.py); never read by codegen, purely a UI
    convenience so a human configuring a downstream node can see a real example
    without needing to re-run or preview first."""
    resultTypes: dict[str, str] = Field(default_factory=dict)
    """User-declared shape ("auto" | "string" | "array" | "object") of this node's
    producesVariable param(s), keyed the same way as resultExamples — lets the
    editor offer object-path suggestions for a downstream field even before this
    node has ever actually been run. Purely a UI hint; never read by codegen."""
    maxAttempts: int = 1
    """How many times to try this node's action before treating it as a real failure
    (the usual __NODE_ERROR__/breakpoint()) — clamped to [1, 5] at codegen time
    (see app/codegen/engine.py). 1 (the default) means no retry, identical generated
    code to before this field existed. Only applies to nodes the engine actually
    wraps in try/except (NodeSpec.to_public_dict's "retryable" — excludes
    block-opening nodes like Loop/If/browser_2captcha/Open Browser, Pause, and
    trigger-category nodes); harmless but a no-op if set on one of those."""
    retryDelaySeconds: float = 0
    """How long to wait (time.sleep) between one failed attempt and the next — only
    meaningful when maxAttempts > 1, clamped to [0, 60] at codegen time. 0 (the
    default) retries immediately, same as before this field existed."""


class WFEdge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: str | None = None
    breakpoint: bool = False


class Workflow(BaseModel):
    id: str
    projectId: str
    name: str
    createdAt: datetime
    updatedAt: datetime
    nodes: list[WFNode] = Field(default_factory=list)
    edges: list[WFEdge] = Field(default_factory=list)
    published: bool = False
    """Whether this workflow is published. The backend scheduler only fires a
    workflow's Schedule Trigger node (see app/execution/scheduler.py) while it's
    published — draft/unpublished workflows never run on a schedule, only manually
    via the Run button. Toggled independently of saving the graph."""
    folderId: str | None = None
    """Which folder (see app/models/folder.py) this workflow is organized under
    within its project — null means the project's root level."""
    startNodeId: str | None = None
    """Which node to treat as the entry point when the graph has more than one node
    with no incoming edges (e.g. a leftover disconnected trigger from earlier edits).
    Only consulted by generate_script (app/codegen/engine.py) when there's genuine
    ambiguity — a single-root graph ignores this field entirely."""
    hasError: bool = False
    """Set when a Schedule/Webhook-triggered (unattended) run of this workflow hits a
    node error — see app/execution/runner.py's _stream_output. Paired with an
    automatic unpublish (nobody is watching an unattended run to fix and retry it), so
    this flags workflows that need maintenance. Cleared on the next successful publish.
    Manual runs and MCP live-session runs never set this — someone is already watching
    those."""


class WorkflowCreate(BaseModel):
    name: str
    folderId: str | None = None


class WorkflowGraph(BaseModel):
    """Payload used for preview/run requests, so unsaved edits can be used."""

    name: str | None = None
    nodes: list[WFNode] = Field(default_factory=list)
    edges: list[WFEdge] = Field(default_factory=list)
    startNodeId: str | None = None


class WorkflowSave(BaseModel):
    name: str
    nodes: list[WFNode] = Field(default_factory=list)
    edges: list[WFEdge] = Field(default_factory=list)
    startNodeId: str | None = None


class WorkflowImport(BaseModel):
    """Payload for creating a new workflow from an exported graph (see the frontend's
    Export button) — same shape as WorkflowSave plus which folder to drop it into."""

    name: str
    nodes: list[WFNode] = Field(default_factory=list)
    edges: list[WFEdge] = Field(default_factory=list)
    folderId: str | None = None
    startNodeId: str | None = None


class VariablePreviewRequest(BaseModel):
    """Payload for previewing a variable's real runtime value — runs the graph up to
    (and including) nodeId, then reports variableName's value."""

    nodes: list[WFNode] = Field(default_factory=list)
    edges: list[WFEdge] = Field(default_factory=list)
    nodeId: str
    variableName: str
    startNodeId: str | None = None
