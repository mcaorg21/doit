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
    def __init__(self, lines: list[bytes], hang_until: asyncio.Event | None = None):
        self.stdout = _FakeStdout(lines)
        self.returncode = None
        # When set, wait() blocks until the test explicitly releases it — models a
        # script genuinely paused at breakpoint() (still alive, not exiting) so a test
        # can inspect state in that window instead of only after the process "exits".
        self._hang_until = hang_until

    async def wait(self):
        if self._hang_until is not None:
            await self._hang_until.wait()
        self.returncode = 0
        return 0


def _make_handle(unattended: bool, lines: list[bytes], hang_until: asyncio.Event | None = None) -> RunHandle:
    record = RunRecord(id="run1", workflowId="wf1", startedAt=runner._now(), status=RunStatus.running, scriptPath="x.py")
    handle = RunHandle(run_id="run1", project_id="proj1", workflow_id="wf1", record=record, unattended=unattended)
    handle.process = _FakeProcess(lines, hang_until=hang_until)
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


# --- Executions should show "Error" the moment a node fails, not just once the
# process eventually exits (a failed node drops into breakpoint() and can sit there
# indefinitely — see app/nodes/*.py's engine auto-wrap) -----------------------------


def test_status_flips_to_error_as_soon_as_a_node_fails_while_process_still_runs():
    hang = asyncio.Event()
    handle = _make_handle(unattended=False, lines=[b"__NODE_ERROR__n1\n"], hang_until=hang)

    async def scenario():
        task = asyncio.create_task(runner._stream_output(handle))
        # Nothing in the stdout-iteration loop actually suspends back to the event
        # loop (see _FakeStdout._gen and asyncio.Queue.put's non-blocking fast path),
        # so one scheduling tick is enough to reach process.wait() — the real
        # suspension point — with the error line already processed.
        await asyncio.sleep(0)
        assert handle.record.status == RunStatus.error
        assert handle.record.finishedAt is None  # the "process" hasn't exited yet
        hang.set()
        await task

    asyncio.run(scenario())
    # A later clean exit (exit code 0, not cancelled) still reports the real outcome.
    assert handle.record.status == RunStatus.success
    assert handle.record.finishedAt is not None


def test_status_stays_error_when_the_process_never_recovers(monkeypatch):
    monkeypatch.setattr(workflow_store, "get_workflow", lambda p, w: SimpleNamespace(published=False))
    handle = _make_handle(unattended=False, lines=[b"__NODE_ERROR__n1\n"])
    handle.process.returncode = None

    # Simulate the process actually exiting non-zero (e.g. stopped/killed later)
    # instead of the fake's default clean exit.
    async def wait():
        return 1

    handle.process.wait = wait
    asyncio.run(runner._stream_output(handle))
    assert handle.record.status == RunStatus.error


def test_pause_node_alone_does_not_flip_status_to_error(monkeypatch):
    calls = []
    monkeypatch.setattr(workflow_store, "set_published", lambda p, w, v: calls.append(("set_published", v)))
    monkeypatch.setattr(workflow_store, "set_error_state", lambda p, w, v: calls.append(("set_error_state", v)))

    # A deliberate Pause node prints __NODE_PAUSED__, never __NODE_ERROR__ (see
    # app/nodes/pause.py) — it's a debugging stop, not a failure, so it must not be
    # reported as one.
    handle = _make_handle(unattended=True, lines=[b"__NODE_PAUSED__n1\n"])
    asyncio.run(runner._stream_output(handle))

    assert calls == []
    assert handle.record.status == RunStatus.success
