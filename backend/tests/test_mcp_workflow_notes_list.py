"""Tests for the MCP list_workflow_notes tool (backend/app/mcp/server.py) — lets an
agent building/editing one workflow see what a PRIOR session already documented in a
SIBLING workflow's notes (same project), so it can reuse a login flow/selectors/data
quirks instead of rediscovering them from scratch. Same fixture pattern as
test_mcp_credentials.py.
"""

import pytest

from app.mcp.server import list_workflow_notes, write_workflow_notes
from app.models.project import ProjectCreate
from app.models.workflow import WorkflowCreate
from app.storage import project_store, workflow_store


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_mcp_workflow_notes_list_project__"))
    yield p
    project_store.delete_project(p.id)


def test_skips_workflows_with_empty_notes(project):
    workflow_store.create_workflow(project.id, WorkflowCreate(name="No notes yet"))
    assert list_workflow_notes(project.id) == []


def test_returns_only_workflows_with_notes(project):
    with_notes = workflow_store.create_workflow(project.id, WorkflowCreate(name="Has notes"))
    workflow_store.create_workflow(project.id, WorkflowCreate(name="No notes"))
    write_workflow_notes(project.id, with_notes.id, "## Login flow\n\nUses #email/#password, confirm on .dashboard.")

    result = list_workflow_notes(project.id)
    assert result == [
        {
            "workflowId": with_notes.id,
            "name": "Has notes",
            "notes": "## Login flow\n\nUses #email/#password, confirm on .dashboard.",
        }
    ]


def test_multiple_workflows_with_notes_all_returned(project):
    a = workflow_store.create_workflow(project.id, WorkflowCreate(name="Report 1"))
    b = workflow_store.create_workflow(project.id, WorkflowCreate(name="Report 2"))
    write_workflow_notes(project.id, a.id, "notes for a")
    write_workflow_notes(project.id, b.id, "notes for b")

    result = list_workflow_notes(project.id)
    assert {r["workflowId"] for r in result} == {a.id, b.id}
    assert {r["name"] for r in result} == {"Report 1", "Report 2"}


def test_empty_project_returns_empty_list():
    p = project_store.create_project(ProjectCreate(name="__test_mcp_workflow_notes_list_empty__"))
    try:
        assert list_workflow_notes(p.id) == []
    finally:
        project_store.delete_project(p.id)


def test_unknown_project_raises():
    with pytest.raises(ValueError):
        list_workflow_notes("proj_does_not_exist")
