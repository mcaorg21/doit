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


def test_reference_workflows_block_names_workflow_and_tells_agent_to_fetch_notes(project):
    ref = workflow_store.create_workflow(project.id, WorkflowCreate(name="Extração PAN - Relatório 1"))
    workflow_store.set_workflow_notes(project.id, ref.id, "Login usa #email/#senha, confirma em .dashboard.")

    block = launch._reference_workflows_block(project.id, [ref.id])
    assert block is not None
    assert "Extração PAN - Relatório 1" in block
    assert ref.id in block
    assert "get_workflow" in block
    # The notes TEXT itself must never be embedded directly here — cmd.exe silently
    # truncates any single .bat line at ~8191 chars, and a real workflow's notes can
    # easily blow past that (confirmed live). The agent fetches it via MCP instead,
    # which has no such limit.
    assert "Login usa #email/#senha" not in block


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
    assert "Relatório 2" in prompt
    assert ref.id in prompt
    assert "Particularidade: paginação por cursor." not in prompt  # fetched via MCP, not embedded
    assert prompt.index("list_workflow_notes") < prompt.index(ref.id)


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


# --- cmd.exe's ~8191-char single-line limit (confirmed live, not just documented) --


def test_write_launch_script_truncates_an_oversized_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "REPO_ROOT", tmp_path)
    huge_prompt = "x" * 20000
    script_path = launch._write_launch_script("codex", huge_prompt)
    content = open(script_path, encoding="utf-8").read()
    try:
        lines = [line for line in content.splitlines() if line.startswith("codex ")]
        assert len(lines) == 1
        assert len(lines[0]) <= launch._MAX_BATCH_LINE_LENGTH
        assert "prompt truncado" in lines[0]
    finally:
        import os

        os.remove(script_path)


def test_write_launch_script_does_not_touch_a_normal_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "REPO_ROOT", tmp_path)
    script_path = launch._write_launch_script("claude", "instrucao curta")
    content = open(script_path, encoding="utf-8").read()
    try:
        assert "prompt truncado" not in content
        assert "instrucao curta" in content
    finally:
        import os

        os.remove(script_path)


def test_reference_workflow_with_huge_notes_never_blows_the_line_limit(project, tmp_path, monkeypatch):
    # Regression test for the real bug: a genuinely huge notes doc (this project's
    # actual multi-session notes were ~10KB) used to get embedded directly into the
    # `codex "..."` line, silently corrupting the launch once cmd.exe truncated it
    # past ~8191 chars. Now the reference block only names the workflow — this just
    # confirms the whole pipeline (prompt build -> .bat write) stays safe regardless.
    monkeypatch.setattr(launch, "REPO_ROOT", tmp_path)
    ref = workflow_store.create_workflow(project.id, WorkflowCreate(name="Relatorio com notes enormes"))
    workflow_store.set_workflow_notes(project.id, ref.id, "nota de sessao de construcao " * 500)
    editing = workflow_store.create_workflow(project.id, WorkflowCreate(name="Relatorio novo"))

    prompt = launch._initial_prompt(project.id, editing.id, reference_workflow_ids=[ref.id])
    script_path = launch._write_launch_script("codex", prompt)
    content = open(script_path, encoding="utf-8").read()
    try:
        lines = [line for line in content.splitlines() if line.startswith("codex ")]
        assert len(lines) == 1
        assert len(lines[0]) <= launch._MAX_BATCH_LINE_LENGTH
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


def test_launch_terminal_endpoint_references_workflow_by_name_not_full_notes(monkeypatch, project):
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
    assert ref.id in captured["prompt"]
    assert "Seletor de login: #email / #senha" not in captured["prompt"]
    assert "get_workflow" in captured["prompt"]
