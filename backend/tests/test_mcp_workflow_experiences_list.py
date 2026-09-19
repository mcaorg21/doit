"""Tests for the MCP list_workflow_experiences tool (backend/app/mcp/server.py) —
lets an agent building/editing one workflow see what a PRIOR session already
learned in a SIBLING workflow's experience log (same project), so it can reuse a
login flow/selectors/data quirks instead of rediscovering them from scratch.
Reads `experience` specifically, never `notes`/Instruções (a sibling's spec may
describe a completely unrelated routine). Same fixture pattern as
test_mcp_credentials.py.
"""

import pytest

from app.mcp.server import list_workflow_experiences, write_workflow_experience
from app.models.project import ProjectCreate
from app.models.workflow import WorkflowCreate
from app.storage import project_store, workflow_store


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_mcp_workflow_experiences_list_project__"))
    yield p
    project_store.delete_project(p.id)


def test_skips_workflows_with_no_experience(project):
    workflow_store.create_workflow(project.id, WorkflowCreate(name="No experience yet"))
    assert list_workflow_experiences(project.id) == []


def test_ignores_instructions_only_workflows(project):
    # A workflow can have rich `notes` (Instruções) but zero `experience` — it
    # shouldn't show up here just because it has SOME documentation.
    w = workflow_store.create_workflow(project.id, WorkflowCreate(name="Only instructions"))
    workflow_store.set_workflow_notes(project.id, w.id, "# Rotina\n\nFaça login e extraia o relatório.")
    assert list_workflow_experiences(project.id) == []


def test_returns_only_workflows_with_experience(project):
    with_experience = workflow_store.create_workflow(project.id, WorkflowCreate(name="Has experience"))
    workflow_store.create_workflow(project.id, WorkflowCreate(name="No experience"))
    write_workflow_experience(
        project.id, with_experience.id, "## Login flow\n\nUses #email/#password, confirm on .dashboard."
    )

    result = list_workflow_experiences(project.id)
    assert result == [
        {
            "workflowId": with_experience.id,
            "name": "Has experience",
            "experience": "## Login flow\n\nUses #email/#password, confirm on .dashboard.",
        }
    ]


def test_multiple_workflows_with_experience_all_returned(project):
    a = workflow_store.create_workflow(project.id, WorkflowCreate(name="Report 1"))
    b = workflow_store.create_workflow(project.id, WorkflowCreate(name="Report 2"))
    write_workflow_experience(project.id, a.id, "experience for a")
    write_workflow_experience(project.id, b.id, "experience for b")

    result = list_workflow_experiences(project.id)
    assert {r["workflowId"] for r in result} == {a.id, b.id}
    assert {r["name"] for r in result} == {"Report 1", "Report 2"}


def test_empty_project_returns_empty_list():
    p = project_store.create_project(ProjectCreate(name="__test_mcp_workflow_experiences_list_empty__"))
    try:
        assert list_workflow_experiences(p.id) == []
    finally:
        project_store.delete_project(p.id)


def test_unknown_project_raises():
    with pytest.raises(ValueError):
        list_workflow_experiences("proj_does_not_exist")
