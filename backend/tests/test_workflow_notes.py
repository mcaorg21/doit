"""Tests for the per-workflow "Notes" markdown doc (backend/app/storage/
workflow_store.py::get_workflow_notes/set_workflow_notes) — a real sibling .md file
next to <workflow_id>.json, not a field inside the workflow's own JSON, and its
exposure through the MCP get_workflow tool's `notes` field (app/mcp/server.py).
"""

import pytest

from app.config import workflows_dir
from app.models.project import ProjectCreate
from app.models.workflow import WorkflowCreate
from app.storage import project_store, workflow_store


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_workflow_notes_project__"))
    yield p
    project_store.delete_project(p.id)


@pytest.fixture()
def workflow(project):
    return workflow_store.create_workflow(project.id, WorkflowCreate(name="notes test flow"))


def test_notes_default_to_empty_string(project, workflow):
    assert workflow_store.get_workflow_notes(project.id, workflow.id) == ""


def test_set_then_get_round_trips(project, workflow):
    text = "# Login flow\n\nUses the `login` credential named 'prod-account'.\n"
    workflow_store.set_workflow_notes(project.id, workflow.id, text)
    assert workflow_store.get_workflow_notes(project.id, workflow.id) == text


def test_notes_are_a_real_sibling_md_file(project, workflow):
    workflow_store.set_workflow_notes(project.id, workflow.id, "hello")
    md_path = workflows_dir(project.id) / f"{workflow.id}.md"
    assert md_path.exists()
    assert md_path.read_text(encoding="utf-8") == "hello"


def test_clearing_notes_removes_the_file(project, workflow):
    workflow_store.set_workflow_notes(project.id, workflow.id, "hello")
    md_path = workflows_dir(project.id) / f"{workflow.id}.md"
    assert md_path.exists()

    workflow_store.set_workflow_notes(project.id, workflow.id, "   ")  # whitespace-only
    assert not md_path.exists()
    assert workflow_store.get_workflow_notes(project.id, workflow.id) == ""


def test_notes_survive_a_graph_save_untouched(project, workflow):
    from app.models.workflow import WorkflowSave

    workflow_store.set_workflow_notes(project.id, workflow.id, "important context")
    workflow_store.save_workflow(
        project.id, workflow.id, WorkflowSave(name="renamed", nodes=[], edges=[], startNodeId=None)
    )
    assert workflow_store.get_workflow_notes(project.id, workflow.id) == "important context"


def test_delete_workflow_removes_its_notes_file_too(project, workflow):
    workflow_store.set_workflow_notes(project.id, workflow.id, "hello")
    md_path = workflows_dir(project.id) / f"{workflow.id}.md"
    assert md_path.exists()

    workflow_store.delete_workflow(project.id, workflow.id)
    assert not md_path.exists()


def test_duplicate_workflow_copies_notes(project, workflow):
    workflow_store.set_workflow_notes(project.id, workflow.id, "copy me")
    duplicate = workflow_store.duplicate_workflow(project.id, workflow.id)
    assert workflow_store.get_workflow_notes(project.id, duplicate.id) == "copy me"


def test_get_workflow_notes_404s_for_missing_workflow(project):
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        workflow_store.get_workflow_notes(project.id, "wf_does_not_exist")


# --- MCP exposure ------------------------------------------------------------


def test_mcp_get_workflow_includes_notes(project, workflow):
    from app.mcp.server import get_workflow as mcp_get_workflow

    workflow_store.set_workflow_notes(project.id, workflow.id, "guidance for the agent")
    result = mcp_get_workflow(project.id, workflow.id)
    assert result.notes == "guidance for the agent"
    assert result.id == workflow.id


def test_mcp_get_workflow_notes_default_empty(project, workflow):
    from app.mcp.server import get_workflow as mcp_get_workflow

    result = mcp_get_workflow(project.id, workflow.id)
    assert result.notes == ""
