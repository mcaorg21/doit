"""Tests for the MCP write_workflow_notes tool (backend/app/mcp/server.py) — the
write counterpart to get_workflow's read-only `notes` field, backed by the same
sibling .md file the editor's Notes modal reads/writes
(backend/app/storage/workflow_store.py).
"""

import pytest

from app.mcp.server import write_workflow_notes
from app.models.project import ProjectCreate
from app.models.workflow import WorkflowCreate
from app.storage import project_store, workflow_store


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_write_workflow_notes_project__"))
    yield p
    project_store.delete_project(p.id)


@pytest.fixture()
def workflow(project):
    return workflow_store.create_workflow(project.id, WorkflowCreate(name="write notes test"))


def test_writes_into_empty_notes(project, workflow):
    result = write_workflow_notes(project.id, workflow.id, "Built a login flow.")
    assert result.mode == "append"
    assert result.notes == "Built a login flow.\n"
    assert workflow_store.get_workflow_notes(project.id, workflow.id) == "Built a login flow.\n"


def test_append_preserves_existing_human_notes(project, workflow):
    workflow_store.set_workflow_notes(project.id, workflow.id, "# Human notes\n\nDon't touch the retry count.\n")
    result = write_workflow_notes(project.id, workflow.id, "## Voice session\n\nAdded a Save Cookies node.")
    assert "Don't touch the retry count." in result.notes
    assert "Added a Save Cookies node." in result.notes
    assert result.notes.index("Human notes") < result.notes.index("Voice session")
    assert "---" in result.notes


def test_replace_overwrites_existing_notes(project, workflow):
    workflow_store.set_workflow_notes(project.id, workflow.id, "old notes that should be gone")
    result = write_workflow_notes(project.id, workflow.id, "brand new notes", mode="replace")
    assert result.mode == "replace"
    assert result.notes == "brand new notes\n"
    assert "old notes" not in result.notes


def test_unknown_workflow_raises(project):
    with pytest.raises(ValueError):
        write_workflow_notes(project.id, "no_such_workflow", "summary")


def test_invalid_mode_raises(project, workflow):
    with pytest.raises(ValueError, match="mode"):
        write_workflow_notes(project.id, workflow.id, "summary", mode="bogus")
