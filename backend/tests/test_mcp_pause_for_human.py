"""Tests for the MCP pause_for_human tool (backend/app/mcp/server.py) — the "I'm
stuck mid-build" escape hatch: records a Pause node right after the live session's
last successful step and leaves the live browser exactly as it is (open, paused),
instead of the agent giving up silently or closing the session.

Uses a REAL live session (a real, if headless, Playwright process paused at pdb) —
this is what actually proves pause_for_human doesn't touch the underlying process,
not just that it mutates the right JSON.
"""

import asyncio

import pytest

from app.mcp.server import finish_live_session, pause_for_human, start_live_session
from app.mcp import live_sessions
from app.models.project import ProjectCreate
from app.models.workflow import WorkflowCreate
from app.storage import project_store, workflow_store


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_pause_for_human_project__"))
    yield p
    project_store.delete_project(p.id)


@pytest.fixture()
def workflow(project):
    return workflow_store.create_workflow(project.id, WorkflowCreate(name="pause for human test"))


def test_raises_when_no_live_session(project, workflow):
    with pytest.raises(ValueError, match="No live session"):
        asyncio.run(pause_for_human(project.id, workflow.id, "stuck on something"))


def test_pause_for_human_records_node_and_leaves_browser_open(project, workflow):
    async def scenario():
        session_result = await start_live_session(project.id, workflow.id, headless=True)
        session = live_sessions.get_session(workflow.id)
        process = session.handle.process
        open_browser_node_id = session_result.openBrowserNode.id

        result = await pause_for_human(project.id, workflow.id, "Status field uses a custom Panjud combobox")

        try:
            assert result.node.type == "pause"
            assert result.node.note == "Status field uses a custom Panjud combobox"
            assert result.edge is not None
            assert result.edge.source == open_browser_node_id
            assert result.edge.target == result.node.id

            # The underlying process must be completely untouched — still alive and
            # paused, not killed or advanced — proving pause_for_human is pure
            # bookkeeping and never sends anything to the live process.
            assert process.returncode is None

            saved = workflow_store.get_workflow(project.id, workflow.id)
            assert [n.type for n in saved.nodes] == ["open_browser", "pause"]
            assert len(saved.edges) == 1

            # The session's own cursor must have moved to the new Pause node, so a
            # SUBSEQUENT pause_for_human (or demo_node) call chains from here, not
            # from the stale open_browser node.
            assert session.last_node_id == result.node.id
        finally:
            await finish_live_session(project.id, workflow.id)

    asyncio.run(scenario())


def test_second_pause_for_human_chains_from_the_first(project, workflow):
    async def scenario():
        await start_live_session(project.id, workflow.id, headless=True)
        first = await pause_for_human(project.id, workflow.id, "first blocker")
        try:
            second = await pause_for_human(project.id, workflow.id, "second blocker")
            assert second.edge is not None
            assert second.edge.source == first.node.id

            saved = workflow_store.get_workflow(project.id, workflow.id)
            assert len(saved.nodes) == 3
            assert len(saved.edges) == 2
        finally:
            await finish_live_session(project.id, workflow.id)

    asyncio.run(scenario())
