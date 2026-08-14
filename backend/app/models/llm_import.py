from pydantic import BaseModel, Field

from app.models.workflow import WFEdge, WFNode


class ReconstructPythonRequest(BaseModel):
    """Payload for turning an arbitrary Python automation script into a workflow
    graph via an LLM — see app/services/workflow_reconstructor.py."""

    code: str
    credentialId: str
    """A project credential of type "openai" or "anthropic" — its value is the API key."""


class ReconstructPythonResponse(BaseModel):
    """Nothing is persisted yet — the frontend shows this as a preview, lets the user
    edit the name/folder, then calls the existing POST .../workflows/import endpoint
    with {name, nodes, edges} to actually create the workflow."""

    name: str
    nodes: list[WFNode] = Field(default_factory=list)
    edges: list[WFEdge] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unknownCount: int = 0
