"""Tests for the MCP write_workflow_experience tool (backend/app/mcp/server.py) —
the write counterpart to get_workflow's read-only `experience` field, backed by the
Experiência Adquirida sibling .md file the editor's Notes modal reads/writes
(backend/app/storage/workflow_store.py). Separate from `notes`/Instruções, the
human-written spec file — this tool never touches that one.
"""

import pytest

from app.execution import workflow_events
from app.mcp.server import write_workflow_experience
from app.models.project import ProjectCreate
from app.models.workflow import WorkflowCreate
from app.storage import project_store, workflow_store


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_write_workflow_experience_project__"))
    yield p
    project_store.delete_project(p.id)


@pytest.fixture()
def workflow(project):
    return workflow_store.create_workflow(project.id, WorkflowCreate(name="write experience test"))


def test_writes_into_empty_experience(project, workflow):
    result = write_workflow_experience(project.id, workflow.id, "Built a login flow.")
    assert result.mode == "append"
    assert result.experience == "Built a login flow.\n"
    assert workflow_store.get_workflow_experience(project.id, workflow.id) == "Built a login flow.\n"


def test_append_preserves_earlier_session_summaries(project, workflow):
    workflow_store.set_workflow_experience(project.id, workflow.id, "## Sessão 1\n\nLogin funciona com #email/#senha.\n")
    result = write_workflow_experience(project.id, workflow.id, "## Sessão 2\n\nAdded a Save Cookies node.")
    assert "Login funciona com #email/#senha." in result.experience
    assert "Added a Save Cookies node." in result.experience
    assert result.experience.index("Sessão 1") < result.experience.index("Sessão 2")
    assert "---" in result.experience


def test_replace_overwrites_existing_experience(project, workflow):
    workflow_store.set_workflow_experience(project.id, workflow.id, "old experience that should be gone")
    result = write_workflow_experience(project.id, workflow.id, "brand new experience", mode="replace")
    assert result.mode == "replace"
    assert result.experience == "brand new experience\n"
    assert "old experience" not in result.experience


def test_never_touches_the_instructions_file(project, workflow):
    # notes.md (Instruções) is the human-written spec — write_workflow_experience
    # must never write there, only to the separate experience.md.
    workflow_store.set_workflow_notes(project.id, workflow.id, "# Instruções originais\n\nFaça login e extraia dados.")
    write_workflow_experience(project.id, workflow.id, "Sessão de construção concluída.")
    assert workflow_store.get_workflow_notes(project.id, workflow.id) == "# Instruções originais\n\nFaça login e extraia dados."


def test_unknown_workflow_raises(project):
    with pytest.raises(ValueError):
        write_workflow_experience(project.id, "no_such_workflow", "summary")


def test_invalid_mode_raises(project, workflow):
    with pytest.raises(ValueError, match="mode"):
        write_workflow_experience(project.id, workflow.id, "summary", mode="bogus")


def test_publishes_workflow_experience_written_event(project, workflow):
    """The editor's "Building..." banner listens for this to clear itself once a
    build session wraps up — see EditorPage.tsx's workflow_experience_written case."""
    queue = workflow_events.subscribe(workflow.id)
    try:
        write_workflow_experience(project.id, workflow.id, "Built a login flow.")
        event = queue.get_nowait()
        assert event == {"type": "workflow_experience_written"}
    finally:
        workflow_events.unsubscribe(workflow.id, queue)
