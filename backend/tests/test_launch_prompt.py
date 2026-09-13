"""Tests for the voice-dictated launch prompt (backend/app/api/launch.py) —
_initial_prompt's new `instruction` handling, the batch-arg sanitization it needs
(free-form dictated text, not just alnum ids, now flows into the generated .bat),
and the /api/launch/terminal endpoint accepting that instruction end to end.

No real terminal is opened or CLI invoked — os.startfile and the MCP-registration
subprocess calls are monkeypatched out, same spirit as the rest of this module's own
"local dev convenience" framing (module docstring).
"""

from fastapi.testclient import TestClient

from app.api import launch
from app.main import app


def test_initial_prompt_without_instruction_is_unchanged_in_spirit():
    prompt = launch._initial_prompt("proj_1", "wf_1")
    assert prompt is not None
    assert "get_workflow" in prompt
    assert "write_workflow_notes" in prompt
    assert "ask_human_voice" not in prompt  # only mentioned for voice-guided sessions


def test_initial_prompt_returns_none_without_both_ids():
    assert launch._initial_prompt(None, None) is None
    assert launch._initial_prompt("proj_1", None) is None


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
