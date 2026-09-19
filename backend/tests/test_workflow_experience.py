"""Tests for the per-workflow "Experiência Adquirida" markdown doc
(backend/app/storage/workflow_store.py::get_workflow_experience/
set_workflow_experience) — a real sibling .md file next to <workflow_id>.json AND
next to <workflow_id>.md (Instruções/notes), not a field inside the workflow's own
JSON, and its exposure through the MCP get_workflow tool's `experience` field
(app/mcp/server.py). Mirrors test_workflow_notes.py's coverage for the instructions
half, plus REST endpoint tests for both docs (not covered elsewhere).
"""

import pytest
from fastapi.testclient import TestClient

from app.config import workflows_dir
from app.main import app
from app.models.project import ProjectCreate
from app.models.workflow import WorkflowCreate
from app.storage import project_store, workflow_store


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_workflow_experience_project__"))
    yield p
    project_store.delete_project(p.id)


@pytest.fixture()
def workflow(project):
    return workflow_store.create_workflow(project.id, WorkflowCreate(name="experience test flow"))


def test_experience_defaults_to_empty_string(project, workflow):
    assert workflow_store.get_workflow_experience(project.id, workflow.id) == ""


def test_set_then_get_round_trips(project, workflow):
    text = "## Sessão 1\n\nLogin funciona com a credencial 'prod-account'.\n"
    workflow_store.set_workflow_experience(project.id, workflow.id, text)
    assert workflow_store.get_workflow_experience(project.id, workflow.id) == text


def test_experience_is_a_real_sibling_md_file_distinct_from_notes(project, workflow):
    workflow_store.set_workflow_notes(project.id, workflow.id, "instrucoes")
    workflow_store.set_workflow_experience(project.id, workflow.id, "experiencia")
    notes_path = workflows_dir(project.id) / f"{workflow.id}.md"
    experience_path = workflows_dir(project.id) / f"{workflow.id}.experience.md"
    assert notes_path.exists() and experience_path.exists()
    assert notes_path.read_text(encoding="utf-8") == "instrucoes"
    assert experience_path.read_text(encoding="utf-8") == "experiencia"


def test_clearing_experience_removes_the_file(project, workflow):
    workflow_store.set_workflow_experience(project.id, workflow.id, "hello")
    experience_path = workflows_dir(project.id) / f"{workflow.id}.experience.md"
    assert experience_path.exists()

    workflow_store.set_workflow_experience(project.id, workflow.id, "   ")  # whitespace-only
    assert not experience_path.exists()
    assert workflow_store.get_workflow_experience(project.id, workflow.id) == ""


def test_experience_survives_a_graph_save_untouched(project, workflow):
    from app.models.workflow import WorkflowSave

    workflow_store.set_workflow_experience(project.id, workflow.id, "important context")
    workflow_store.save_workflow(
        project.id, workflow.id, WorkflowSave(name="renamed", nodes=[], edges=[], startNodeId=None)
    )
    assert workflow_store.get_workflow_experience(project.id, workflow.id) == "important context"


def test_delete_workflow_removes_its_experience_file_too(project, workflow):
    workflow_store.set_workflow_experience(project.id, workflow.id, "hello")
    experience_path = workflows_dir(project.id) / f"{workflow.id}.experience.md"
    assert experience_path.exists()

    workflow_store.delete_workflow(project.id, workflow.id)
    assert not experience_path.exists()


def test_duplicate_workflow_copies_experience_too(project, workflow):
    workflow_store.set_workflow_notes(project.id, workflow.id, "copy notes")
    workflow_store.set_workflow_experience(project.id, workflow.id, "copy experience")
    duplicate = workflow_store.duplicate_workflow(project.id, workflow.id)
    assert workflow_store.get_workflow_notes(project.id, duplicate.id) == "copy notes"
    assert workflow_store.get_workflow_experience(project.id, duplicate.id) == "copy experience"


def test_get_workflow_experience_404s_for_missing_workflow(project):
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        workflow_store.get_workflow_experience(project.id, "wf_does_not_exist")


# --- MCP exposure ------------------------------------------------------------


def test_mcp_get_workflow_includes_both_notes_and_experience(project, workflow):
    from app.mcp.server import get_workflow as mcp_get_workflow

    workflow_store.set_workflow_notes(project.id, workflow.id, "instrucoes pro agente")
    workflow_store.set_workflow_experience(project.id, workflow.id, "o que a sessao anterior aprendeu")
    result = mcp_get_workflow(project.id, workflow.id)
    assert result.notes == "instrucoes pro agente"
    assert result.experience == "o que a sessao anterior aprendeu"
    assert result.id == workflow.id


def test_mcp_get_workflow_experience_default_empty(project, workflow):
    from app.mcp.server import get_workflow as mcp_get_workflow

    result = mcp_get_workflow(project.id, workflow.id)
    assert result.experience == ""


# --- REST endpoints (GET/PUT .../notes and .../experience) -----------------------

client = TestClient(app)


def test_rest_notes_and_experience_are_independent(project, workflow):
    base = f"/api/projects/{project.id}/workflows/{workflow.id}"

    r1 = client.put(f"{base}/notes", json={"notes": "instrucoes via REST"})
    assert r1.status_code == 200
    r2 = client.put(f"{base}/experience", json={"experience": "experiencia via REST"})
    assert r2.status_code == 200

    assert client.get(f"{base}/notes").json() == {"notes": "instrucoes via REST"}
    assert client.get(f"{base}/experience").json() == {"experience": "experiencia via REST"}


def test_rest_experience_defaults_to_empty(project, workflow):
    base = f"/api/projects/{project.id}/workflows/{workflow.id}"
    assert client.get(f"{base}/experience").json() == {"experience": ""}
