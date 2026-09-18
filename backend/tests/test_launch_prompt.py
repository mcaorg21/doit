"""Tests for the voice-dictated launch prompt (backend/app/api/launch.py) —
_initial_prompt's new `instruction` handling, the batch-arg sanitization it needs
(free-form dictated text, not just alnum ids, now flows into the generated .bat),
and the /api/launch/terminal endpoint accepting that instruction end to end.

No real terminal is opened or CLI invoked — os.startfile and the MCP-registration
subprocess calls are monkeypatched out, same spirit as the rest of this module's own
"local dev convenience" framing (module docstring).
"""

import pytest
from fastapi.testclient import TestClient

from app.api import launch
from app.main import app
from app.models.project import ProjectCreate
from app.models.workflow import WorkflowCreate
from app.storage import project_store, workflow_store


@pytest.fixture()
def project():
    p = project_store.create_project(ProjectCreate(name="__test_launch_reference_workflows_project__"))
    yield p
    project_store.delete_project(p.id)


def test_initial_prompt_without_instruction_is_unchanged_in_spirit():
    prompt = launch._initial_prompt("proj_1", "wf_1")
    assert prompt is not None
    assert "get_workflow" in prompt
    assert "write_workflow_notes" in prompt
    assert "ask_human_voice" not in prompt  # only mentioned for voice-guided sessions


def test_initial_prompt_tells_agent_to_check_sibling_workflows_in_order():
    # Added so an agent building/editing one workflow reuses what a prior session
    # already documented in a SIBLING workflow's notes (same project) instead of
    # rediscovering login flows/selectors/data quirks from scratch each time.
    prompt = launch._initial_prompt("proj_1", "wf_1")
    assert prompt is not None
    assert "list_workflow_notes(project_id='proj_1')" in prompt
    assert prompt.index("get_workflow") < prompt.index("list_workflow_notes")
    assert prompt.index("list_workflow_notes") < prompt.index("write_workflow_notes")


def test_initial_prompt_returns_none_without_both_ids():
    assert launch._initial_prompt(None, None) is None
    assert launch._initial_prompt("proj_1", None) is None


# --- "Pegar experiência de outro workflow" (referenceWorkflowIds) ----------------


def test_reference_workflows_block_embeds_name_and_notes(project):
    ref = workflow_store.create_workflow(project.id, WorkflowCreate(name="Extração PAN - Relatório 1"))
    workflow_store.set_workflow_notes(project.id, ref.id, "Login usa #email/#senha, confirma em .dashboard.")

    block = launch._reference_workflows_block(project.id, [ref.id])
    assert block is not None
    assert "Extração PAN - Relatório 1" in block
    assert ref.id in block
    assert "Login usa #email/#senha" in block


def test_reference_workflows_block_skips_workflow_with_no_notes(project):
    ref = workflow_store.create_workflow(project.id, WorkflowCreate(name="Sem notes ainda"))
    assert launch._reference_workflows_block(project.id, [ref.id]) is None


def test_reference_workflows_block_skips_nonexistent_workflow(project):
    assert launch._reference_workflows_block(project.id, ["wf_does_not_exist"]) is None


def test_initial_prompt_includes_reference_block_after_list_workflow_notes(project):
    ref = workflow_store.create_workflow(project.id, WorkflowCreate(name="Relatório 2"))
    workflow_store.set_workflow_notes(project.id, ref.id, "Particularidade: paginação por cursor.")
    editing = workflow_store.create_workflow(project.id, WorkflowCreate(name="Relatório 3 (novo)"))

    prompt = launch._initial_prompt(project.id, editing.id, reference_workflow_ids=[ref.id])
    assert prompt is not None
    assert "Particularidade: paginação por cursor." in prompt
    assert prompt.index("list_workflow_notes") < prompt.index("Particularidade: paginação por cursor.")


def test_initial_prompt_without_reference_workflows_has_no_extra_block():
    prompt = launch._initial_prompt("proj_1", "wf_1", reference_workflow_ids=None)
    assert prompt is not None
    prompt_empty_list = launch._initial_prompt("proj_1", "wf_1", reference_workflow_ids=[])
    assert prompt == prompt_empty_list


def test_initial_prompt_tells_agent_to_continue_not_rebuild():
    """Prevents the agent from treating a dictated instruction like "cria um workflow
    que faz X" as license to recreate everything from scratch when a prior session
    already left nodes/notes behind."""
    prompt = launch._initial_prompt("proj_1", "wf_1", instruction="cria um workflow que faz X")
    assert prompt is not None
    assert "CONTINUE a partir do que ja esta la" in prompt
    assert "nao recrie o workflow do zero" in prompt
    assert "nao como uma" in prompt  # dictated instruction framed as next step, not full spec
    assert 'mode="append"' in prompt


def test_initial_prompt_defaults_to_portuguese_node_titles():
    prompt = launch._initial_prompt("proj_1", "wf_1")
    assert prompt is not None
    assert "escreva em portugues" in prompt
    assert "write it in English" not in prompt


def test_initial_prompt_with_english_language_tells_agent_to_use_english():
    prompt = launch._initial_prompt("proj_1", "wf_1", language="en")
    assert prompt is not None
    assert "write it in English" in prompt
    assert "escreva em portugues" not in prompt


def test_initial_prompt_with_instruction_mentions_voice_loop_in_order():
    prompt = launch._initial_prompt("proj_1", "wf_1", instruction="abre o navegador e vai pro google")
    assert prompt is not None
    assert "abre o navegador e vai pro google" in prompt
    assert prompt.index("get_workflow") < prompt.index("abre o navegador e vai pro google")
    assert prompt.index("abre o navegador e vai pro google") < prompt.index("ask_human_voice")
    assert prompt.index("ask_human_voice") < prompt.index("write_workflow_notes")


def test_sanitize_for_batch_arg_swaps_quotes_doubles_percent_collapses_newlines():
    raw = 'diz "oi" pra 100% dos usuarios\ne clica em enviar'
    cleaned = launch._sanitize_for_batch_arg(raw)
    assert '"' not in cleaned
    assert "'oi'" in cleaned
    assert "100%% dos usuarios" in cleaned
    assert "\n" not in cleaned


def test_write_launch_script_embeds_sanitized_prompt_and_sets_codepage(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "REPO_ROOT", tmp_path)
    prompt = launch._initial_prompt("proj_1", "wf_1", instruction='diz "oi" com 100% de certeza')
    script_path = launch._write_launch_script("claude", prompt)
    content = open(script_path, encoding="utf-8").read()
    try:
        assert "chcp 65001" in content
        lines = [line for line in content.splitlines() if line.startswith("claude ")]
        assert len(lines) == 1
        assert '"' in lines[0]  # the outer quoting around the whole prompt is intact
        assert "100%%" in lines[0]  # inner literal % doubled, still a single line
    finally:
        import os

        os.remove(script_path)


def test_launch_terminal_endpoint_accepts_instruction(monkeypatch):
    monkeypatch.setattr(launch, "_ensure_mcp_registered", lambda provider: (True, "MCP server already registered"))
    captured: dict = {}

    def fake_write_script(provider, prompt):
        captured["provider"] = provider
        captured["prompt"] = prompt
        return "C:/fake/path.bat"

    monkeypatch.setattr(launch, "_write_launch_script", fake_write_script)
    monkeypatch.setattr(launch.os, "startfile", lambda path: None, raising=False)

    client = TestClient(app)
    response = client.post(
        "/api/launch/terminal",
        json={
            "provider": "claude",
            "projectId": "proj_1",
            "workflowId": "wf_1",
            "instruction": "cria um workflow de login",
        },
    )
    assert response.status_code == 200
    assert response.json()["launched"] is True
    assert "cria um workflow de login" in captured["prompt"]
    assert "ask_human_voice" in captured["prompt"]


def test_launch_terminal_endpoint_embeds_reference_workflow_notes(monkeypatch, project):
    ref = workflow_store.create_workflow(project.id, WorkflowCreate(name="Extração PAN - Relatório 1"))
    workflow_store.set_workflow_notes(project.id, ref.id, "Seletor de login: #email / #senha")
    editing = workflow_store.create_workflow(project.id, WorkflowCreate(name="Extração PAN - Relatório 2"))

    monkeypatch.setattr(launch, "_ensure_mcp_registered", lambda provider: (True, "MCP server already registered"))
    captured: dict = {}

    def fake_write_script(provider, prompt):
        captured["prompt"] = prompt
        return "C:/fake/path.bat"

    monkeypatch.setattr(launch, "_write_launch_script", fake_write_script)
    monkeypatch.setattr(launch.os, "startfile", lambda path: None, raising=False)

    client = TestClient(app)
    response = client.post(
        "/api/launch/terminal",
        json={
            "provider": "claude",
            "projectId": project.id,
            "workflowId": editing.id,
            "referenceWorkflowIds": [ref.id],
        },
    )
    assert response.status_code == 200
    assert "Extração PAN - Relatório 1" in captured["prompt"]
    assert "Seletor de login: #email / #senha" in captured["prompt"]
