"""Tests for capturing __NODE_RESULT__ markers during a real run
(app/execution/runner.py::_stream_output) and persisting them onto the matching
node's resultExamples — see app/codegen/engine.py's _result_capture_lines for how
the marker line itself gets emitted into the generated script.

Same fake-process/monkeypatch approach as test_runner_unattended_error.py.
"""

import asyncio
from types import SimpleNamespace

import pytest

from app.execution import runner
from app.execution.run_manager import RunHandle
from app.models.run import RunRecord, RunStatus
from app.storage import workflow_store
from app.execution import workflow_events


class _FakeStdout:
    def __init__(self, lines: list[bytes]):
        self.lines = lines

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


def _make_handle(lines: list[bytes]) -> RunHandle:
    record = RunRecord(id="run1", workflowId="wf1", startedAt=runner._now(), status=RunStatus.running, scriptPath="x.py")
    handle = RunHandle(run_id="run1", project_id="proj1", workflow_id="wf1", record=record, unattended=False)
    handle.process = _FakeProcess(lines)
    return handle


@pytest.fixture(autouse=True)
def _stub_run_store(monkeypatch):
    monkeypatch.setattr(runner.run_store, "save_run", lambda *a, **k: None)


def test_captures_and_persists_a_result_marker(monkeypatch):
    calls = []
    fake_node = SimpleNamespace(id="n1", resultExamples={"resultVar": "hello world"})
    fake_workflow = SimpleNamespace(nodes=[fake_node])

    def fake_set(project_id, workflow_id, results):
        calls.append(("set_node_result_examples", project_id, workflow_id, results))
        return fake_workflow

    published_events = []
    monkeypatch.setattr(workflow_store, "set_node_result_examples", fake_set)
    monkeypatch.setattr(workflow_events, "publish", lambda wf_id, event: published_events.append((wf_id, event)))

    line = b'__NODE_RESULT__{"nodeId": "n1", "key": "resultVar", "value": "hello world"}\n'
    handle = _make_handle(lines=[line])
    asyncio.run(runner._stream_output(handle))

    assert calls == [("set_node_result_examples", "proj1", "wf1", {"n1": {"resultVar": "hello world"}})]
    assert published_events == [("wf1", {"type": "node_result_captured", "nodeId": "n1", "resultExamples": {"resultVar": "hello world"}})]


def test_multiple_markers_for_different_nodes_and_keys(monkeypatch):
    calls = []
    monkeypatch.setattr(
        workflow_store,
        "set_node_result_examples",
        lambda p, w, results: calls.append(results) or None,
    )
    monkeypatch.setattr(workflow_events, "publish", lambda *a, **k: None)

    lines = [
        b'__NODE_RESULT__{"nodeId": "n1", "key": "resultVar", "value": 42}\n',
        b'__NODE_RESULT__{"nodeId": "n2", "key": "resultVar", "value": [1, 2, 3]}\n',
        b'__NODE_RESULT__{"nodeId": "n2", "key": "base64Var", "value": "abc123"}\n',
    ]
    handle = _make_handle(lines=lines)
    asyncio.run(runner._stream_output(handle))

    assert calls == [{"n1": {"resultVar": 42}, "n2": {"resultVar": [1, 2, 3], "base64Var": "abc123"}}]


def test_malformed_marker_line_does_not_crash_the_run(monkeypatch):
    calls = []
    monkeypatch.setattr(workflow_store, "set_node_result_examples", lambda *a, **k: calls.append(1) or None)
    monkeypatch.setattr(workflow_events, "publish", lambda *a, **k: None)

    handle = _make_handle(lines=[b"__NODE_RESULT__not valid json at all\n"])
    asyncio.run(runner._stream_output(handle))  # must not raise

    assert calls == []


def test_no_result_markers_never_calls_persist(monkeypatch):
    calls = []
    monkeypatch.setattr(workflow_store, "set_node_result_examples", lambda *a, **k: calls.append(1) or None)

    handle = _make_handle(lines=[b"[n1] navigated ok\n"])
    asyncio.run(runner._stream_output(handle))

    assert calls == []
