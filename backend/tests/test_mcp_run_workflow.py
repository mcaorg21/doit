"""Tests for the MCP run_workflow tool (backend/app/mcp/server.py).

Unlike the other node tests in this suite (which exec a codegen fragment in an
isolated namespace), run_workflow drives the SAME machinery a real Run-button click
does — app/storage/project_store.py + app/storage/workflow_store.py (real project/
workflow JSON files under data/projects/, cleaned up by the fixture below) and
app/execution/runner.py's real subprocess spawning. This is deliberate: the whole
point of run_workflow is "does a saved workflow actually run end to end", so the
test exercises that literally rather than mocking any of it.

A goto to a refused local port (http://127.0.0.1:1/) is used for the failure case
instead of, say, a click on a missing selector — Playwright's own actionability
wait for a missing element takes its full default timeout (30s) before failing,
while a real connection refusal surfaces near-instantly, keeping this test fast.
"""

import asyncio

import pytest

from app.mcp.server import run_workflow
from app.models.project import ProjectCreate
from app.models.workflow import Position, WFEdge, WFNode, WorkflowCreate, WorkflowSave
from app.storage import project_store, workflow_store


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_mcp_run_workflow_project__"))
    yield p
    project_store.delete_project(p.id)


def _save(project_id: str, name: str, nodes: list[WFNode], edges: list[WFEdge]) -> str:
    wf = workflow_store.create_workflow(project_id, WorkflowCreate(name=name))
    workflow_store.save_workflow(project_id, wf.id, WorkflowSave(name=name, nodes=nodes, edges=edges, startNodeId=None))
    return wf.id


def test_successful_workflow_reports_ok(project):
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(id="n2", type="goto", position=Position(x=1, y=0), params={"url": "https://example.com"}),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2")]
    workflow_id = _save(project.id, "ok flow", nodes, edges)

    result = asyncio.run(run_workflow(project.id, workflow_id, timeout_seconds=30))

    assert result.ok is True
    assert result.status == "success"
    assert result.failedNodeId is None
    assert result.failedNodeLabel is None
    assert result.errorMessage is None
    assert any("navigated to" in line for line in result.logTail)


def test_broken_node_reports_which_one_and_why(project):
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(
            id="n2",
            type="goto",
            position=Position(x=1, y=0),
            params={"url": "http://127.0.0.1:1/"},
            title="Ir para servico inexistente",
        ),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2")]
    workflow_id = _save(project.id, "broken flow", nodes, edges)

    result = asyncio.run(run_workflow(project.id, workflow_id, timeout_seconds=30))

    assert result.ok is False
    assert result.status == "error"
    assert result.failedNodeId == "n2"
    assert result.failedNodeLabel == "Ir para servico inexistente"
    assert result.errorMessage is not None
    assert "n2" in result.errorMessage or "servico" in result.errorMessage.lower()


def test_reports_error_promptly_not_after_full_timeout(project):
    """Regression guard: once the __NODE_ERROR__ marker + its message arrive, the
    engine's auto-wrap is about to breakpoint() and hang forever (nothing unattended
    can send "continue") — run_workflow must stop the run and return right away
    instead of waiting out the rest of timeout_seconds for nothing."""
    import time

    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(id="n2", type="goto", position=Position(x=1, y=0), params={"url": "http://127.0.0.1:1/"}),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2")]
    workflow_id = _save(project.id, "broken flow fast", nodes, edges)

    start = time.monotonic()
    result = asyncio.run(run_workflow(project.id, workflow_id, timeout_seconds=60))
    elapsed = time.monotonic() - start

    assert result.status == "error"
    assert elapsed < 20, f"took {elapsed:.1f}s — should return promptly after the error marker, well under the 60s timeout"


def test_workflow_with_pause_node_is_rejected_up_front(project):
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(id="n2", type="pause", position=Position(x=1, y=0), params={}),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2")]
    workflow_id = _save(project.id, "paused flow", nodes, edges)

    with pytest.raises(ValueError, match="Pause node"):
        asyncio.run(run_workflow(project.id, workflow_id, timeout_seconds=10))


def test_workflow_with_breakpointed_connector_is_rejected_up_front(project):
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(id="n2", type="goto", position=Position(x=1, y=0), params={"url": "https://example.com"}),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2", breakpoint=True)]
    workflow_id = _save(project.id, "breakpointed connector flow", nodes, edges)

    with pytest.raises(ValueError, match="breakpoint"):
        asyncio.run(run_workflow(project.id, workflow_id, timeout_seconds=10))


def test_invalid_workflow_graph_raises_clear_error(project):
    """A workflow that doesn't even compile (here: a cycle) should surface as a plain
    ValueError, same treatment as validate_workflow's CodegenError handling, not an
    unhandled exception."""
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(id="n2", type="goto", position=Position(x=1, y=0), params={"url": "https://example.com"}),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2"), WFEdge(id="e2", source="n2", target="n1")]
    workflow_id = _save(project.id, "cyclic flow", nodes, edges)

    with pytest.raises(ValueError, match="start node"):
        asyncio.run(run_workflow(project.id, workflow_id, timeout_seconds=10))
