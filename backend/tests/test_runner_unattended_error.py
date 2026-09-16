"""Tests for the auto-unpublish-on-error gating in
app/execution/runner.py::_stream_output (see app/models/workflow.py's hasError field
and app/execution/run_manager.py's RunHandle.unattended).

Only a Schedule/Webhook-triggered ("unattended") run should auto-unpublish + flag
hasError when a node fails — a manual Run-button run or an MCP live-session run has a
human already watching it, so it must NOT be touched. workflow_store is monkeypatched
rather than hitting real project/workflow files on disk, since this test is only
exercising _stream_output's branching, not workflow_store itself.
"""

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.execution import runner
from app.execution.run_manager import RunHandle
from app.models.run import RunRecord, RunStatus
from app.storage import workflow_store


@dataclass
class _FakeStdout:
    lines: list[bytes]

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for line in self.lines:
            yield line


class _FakeProcess:
    def __init__(self, lines: list[bytes]):
        self.stdout = _FakeStdout(lines)
        self.returncode = None

    async def wait(self):
        self.returncode = 0
        return 0


def _make_handle(unattended: bool, lines: list[bytes]) -> RunHandle:
    record = RunRecord(id="run1", workflowId="wf1", startedAt=runner._now(), status=RunStatus.running, scriptPath="x.py")
    handle = RunHandle(run_id="run1", project_id="proj1", workflow_id="wf1", record=record, unattended=unattended)
    handle.process = _FakeProcess(lines)
    return handle


@pytest.fixture(autouse=True)
def _stub_run_store(monkeypatch):
    monkeypatch.setattr(runner.run_store, "save_run", lambda *a, **k: None)


def test_unattended_run_auto_unpublishes_and_flags_error(monkeypatch):
    calls = []
    monkeypatch.setattr(workflow_store, "get_workflow", lambda p, w: SimpleNamespace(published=True))
    monkeypatch.setattr(workflow_store, "set_published", lambda p, w, v: calls.append(("set_published", v)))
    monkeypatch.setattr(workflow_store, "set_error_state", lambda p, w, v: calls.append(("set_error_state", v)))

    handle = _make_handle(unattended=True, lines=[b"__NODE_ERROR__n1\n"])
    asyncio.run(runner._stream_output(handle))

    assert calls == [("set_published", False), ("set_error_state", True)]


def test_manual_run_does_not_touch_publish_state(monkeypatch):
    calls = []
    monkeypatch.setattr(workflow_store, "get_workflow", lambda p, w: calls.append("get_workflow") or SimpleNamespace(published=True))
    monkeypatch.setattr(workflow_store, "set_published", lambda p, w, v: calls.append(("set_published", v)))
    monkeypatch.setattr(workflow_store, "set_error_state", lambda p, w, v: calls.append(("set_error_state", v)))

    handle = _make_handle(unattended=False, lines=[b"__NODE_ERROR__n1\n"])
    asyncio.run(runner._stream_output(handle))

    assert calls == []


def test_unattended_run_with_no_error_stays_untouched(monkeypatch):
    calls = []
    monkeypatch.setattr(workflow_store, "get_workflow", lambda p, w: calls.append("get_workflow") or SimpleNamespace(published=True))
    monkeypatch.setattr(workflow_store, "set_published", lambda p, w, v: calls.append(("set_published", v)))
    monkeypatch.setattr(workflow_store, "set_error_state", lambda p, w, v: calls.append(("set_error_state", v)))

    handle = _make_handle(unattended=True, lines=[b"[n1] navigated ok\n"])
    asyncio.run(runner._stream_output(handle))

    assert calls == []


# --- the dedicated Error node's marker (app/nodes/error.py) ----------------
#
# Unlike NODE_ERROR_MARKER above (an ordinary node crashing, gated on
# `unattended`), WORKFLOW_MARK_ERROR_MARKER always unpublishes + flags the
# workflow — the Error node means it every time it's reached, no matter how
# the run was started.


def test_error_node_marker_unpublishes_on_a_manual_run(monkeypatch):
    calls = []
    monkeypatch.setattr(workflow_store, "set_published", lambda p, w, v: calls.append(("set_published", v)))
    monkeypatch.setattr(workflow_store, "set_error_state", lambda p, w, v: calls.append(("set_error_state", v)))

    handle = _make_handle(unattended=False, lines=[b'__WORKFLOW_MARK_ERROR__{"nodeId": "n1", "message": "boom"}\n'])
    asyncio.run(runner._stream_output(handle))

    assert calls == [("set_published", False), ("set_error_state", True)]


def test_error_node_marker_unpublishes_on_an_unattended_run(monkeypatch):
    calls = []
    monkeypatch.setattr(workflow_store, "get_workflow", lambda p, w: SimpleNamespace(published=True))
    monkeypatch.setattr(workflow_store, "set_published", lambda p, w, v: calls.append(("set_published", v)))
    monkeypatch.setattr(workflow_store, "set_error_state", lambda p, w, v: calls.append(("set_error_state", v)))

    handle = _make_handle(unattended=True, lines=[b'__WORKFLOW_MARK_ERROR__{"nodeId": "n1", "message": "boom"}\n'])
    asyncio.run(runner._stream_output(handle))

    assert calls == [("set_published", False), ("set_error_state", True)]
