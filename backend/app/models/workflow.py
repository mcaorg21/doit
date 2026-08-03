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
