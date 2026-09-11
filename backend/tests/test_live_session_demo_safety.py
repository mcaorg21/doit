"""Tests for the demo-mode indentation safety net added to
app/mcp/live_sessions.py::run_demo_step alongside download_file (see its module
docstring): a node's normal `codegen` fragment must be checked for indentation before
being sent to a live pdb session one line at a time, since pdb's one-line-at-a-time
REPL can't parse a block header without its body arriving as a separate command.

These don't spin up a real live session (no real browser/subprocess) — the
indentation check happens before run_demo_step ever touches session.handle, so a
LiveSession with handle=None is enough to prove the check fires (or doesn't) at the
right point, without the cost of a real Playwright session per test.
"""

import asyncio

import pytest

from app.mcp import live_sessions
from app.mcp.live_sessions import LiveSession, LiveSessionError, run_demo_step


def _fake_session() -> LiveSession:
    return LiveSession(
        workflow_id="__test_wf__",
        project_id="__test_project__",
        handle=None,  # type: ignore[arg-type]  — must not be touched before the indentation check
        browser_var="browser",
        target_var="page",
    )


def test_download_file_is_demoable_via_its_flat_demo_codegen():
    """download_file has a demo_codegen override, so the indentation check on its
    normal (with-block) codegen is skipped entirely — this should get as far as
    trying to talk to session.handle, which is None here, so it fails on THAT
    (an AttributeError from send_input hitting handle=None) rather than on the
    indentation check — proving the check didn't block it."""
    session = _fake_session()
    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            run_demo_step(session, "download_file", {"selector": "#dl", "selectorType": "css"}, "Download File")
        )
    assert not isinstance(exc_info.value, LiveSessionError), (
        f"download_file was rejected by the indentation safety net, but it has a demo_codegen "
        f"and should have bypassed that check entirely: {exc_info.value}"
    )


@pytest.mark.parametrize("node_type", ["save_files", "get_file"])
def test_nodes_with_indented_fragments_and_no_demo_codegen_are_rejected(node_type):
    """save_files (`with open(...) as f:`) and get_file (`if not os.path.exists...:`)
    both have real indented blocks in their normal codegen and no demo_codegen
    override — confirms the retroactive safety net actually catches them, instead of
    silently sending broken multi-line code to a live pdb session."""
    spec = live_sessions.NODE_REGISTRY[node_type]
    assert spec.demo_codegen is None, f"{node_type} unexpectedly has a demo_codegen now — update this test"

    session = _fake_session()
    params = {"files": [{"filename": "x.txt", "value": "aGVsbG8="}]} if node_type == "save_files" else {"filename": "x.txt", "resultVar": "r"}
    with pytest.raises(LiveSessionError, match="indented code block"):
        asyncio.run(run_demo_step(session, node_type, params, "Test"))


def test_upload_file_and_totp_remain_demoable_no_override_needed():
    """Both are already flat (no indentation) without needing a demo_codegen, so the
    safety net should let them through unchanged — regression guard against the new
    check being too aggressive."""
    session = _fake_session()
    for node_type, params in [
        ("upload_file", {"selector": "input", "selectorType": "css", "filePath": "/tmp/x.txt"}),
        # totp needs a real credential to fully run, but the indentation check happens
        # before that resolution — CodegenError (missing credential) surfacing instead
        # of LiveSessionError (indentation) is exactly what proves the check passed.
        ("totp", {"credentialId": "", "resultVar": "code"}),
    ]:
        with pytest.raises(Exception) as exc_info:
            asyncio.run(run_demo_step(session, node_type, params, "Test"))
        assert not isinstance(exc_info.value, LiveSessionError) or "indented code block" not in str(exc_info.value)
