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


class WorkflowCreate(BaseModel):
    name: str


class WorkflowGraph(BaseModel):
    """Payload used for preview/run requests, so unsaved edits can be used."""

    name: str | None = None
    nodes: list[WFNode] = Field(default_factory=list)
    edges: list[WFEdge] = Field(default_factory=list)


class WorkflowSave(BaseModel):
    name: str
    nodes: list[WFNode] = Field(default_factory=list)
    edges: list[WFEdge] = Field(default_factory=list)


class VariablePreviewRequest(BaseModel):
    """Payload for previewing a variable's real runtime value — runs the graph up to
    (and including) nodeId, then reports variableName's value."""

    nodes: list[WFNode] = Field(default_factory=list)
    edges: list[WFEdge] = Field(default_factory=list)
    nodeId: str
    variableName: str
