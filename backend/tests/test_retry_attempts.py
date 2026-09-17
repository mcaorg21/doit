"""Tests for the per-node "Retry Attempts" / "Delay Between Attempts" feature
(backend/app/codegen/engine.py's _wrap_with_retry, backend/app/models/workflow.py's
WFNode.maxAttempts/retryDelaySeconds, backend/app/nodes/base.py's NodeSpec.
to_public_dict "retryable"). maxAttempts=1 (the default) must reproduce the exact
single try/except this app generated before retries existed — most of these tests
exercise the pure retry-loop control flow directly with plain Python fragments (no
Playwright needed for that part; it's generic, not browser-specific), and a couple
go through the real NODE_REGISTRY types to confirm end-to-end wiring.
"""

import sys

from app.codegen.engine import HEADER, _wrap_with_retry, generate_script
from app.models.workflow import Position, WFEdge, WFNode
from app.nodes.registry import NODE_REGISTRY

# --- NodeSpec.to_public_dict's "retryable" -----------------------------------


def test_retryable_true_for_a_plain_action_node():
    assert NODE_REGISTRY["click"].to_public_dict()["retryable"] is True
    assert NODE_REGISTRY["get_text"].to_public_dict()["retryable"] is True


def test_retryable_false_for_block_opening_nodes():
    for node_type in ("loop", "if", "browser_2captcha", "open_browser"):
        assert NODE_REGISTRY[node_type].to_public_dict()["retryable"] is False, node_type


def test_retryable_false_for_pause_and_triggers():
    assert NODE_REGISTRY["pause"].to_public_dict()["retryable"] is False
    assert NODE_REGISTRY["schedule_trigger"].to_public_dict()["retryable"] is False
    assert NODE_REGISTRY["webhook_trigger"].to_public_dict()["retryable"] is False


def test_retryable_true_by_default_for_http_requests_callable_opens_block():
    # http_request's opens_block is a callable (True only when "loop automatically"
    # is on) — the catalog exposes the common/default case (off) as retryable.
    assert NODE_REGISTRY["http_request"].to_public_dict()["retryable"] is True


# --- _wrap_with_retry: pure control-flow shape --------------------------------


def test_one_attempt_reproduces_the_original_single_try_except():
    wrapped = _wrap_with_retry("do_thing()", None, "n1", "My Node", max_attempts=1, retry_delay_seconds=0)
    assert wrapped == (
        "try:\n"
        "    do_thing()\n"
        "except Exception as _e:\n"
        "    print('__NODE_ERROR__n1')\n"
        "    print('Tratar erro no node My Node: ' + str(_e))\n"
        "    breakpoint()"
    )


def test_zero_or_missing_attempts_also_means_one_attempt():
    assert _wrap_with_retry("x()", None, "n1", "N", max_attempts=0, retry_delay_seconds=0) == _wrap_with_retry(
        "x()", None, "n1", "N", max_attempts=1, retry_delay_seconds=0
    )


def test_attempts_clamped_to_five():
    wrapped = _wrap_with_retry("x()", None, "n1", "N", max_attempts=99, retry_delay_seconds=0)
    assert "for _attempt in range(1, 6):" in wrapped


def test_no_sleep_line_when_delay_is_zero():
    wrapped = _wrap_with_retry("x()", None, "n1", "N", max_attempts=3, retry_delay_seconds=0)
    assert "time.sleep" not in wrapped


def test_sleep_line_present_and_clamped_when_delay_given():
    wrapped = _wrap_with_retry("x()", None, "n1", "N", max_attempts=3, retry_delay_seconds=2.5)
    assert "time.sleep(2.5)" in wrapped
    clamped = _wrap_with_retry("x()", None, "n1", "N", max_attempts=3, retry_delay_seconds=999)
    assert "time.sleep(60)" in clamped
    negative = _wrap_with_retry("x()", None, "n1", "N", max_attempts=3, retry_delay_seconds=-5)
    assert "time.sleep" not in negative  # clamped to 0 -> no sleep line at all


def test_retry_fragment_compiles():
    wrapped = _wrap_with_retry("x = 1", None, "n1", "N", max_attempts=3, retry_delay_seconds=1)
    compile(wrapped, "<fragment>", "exec")


# --- Real execution: the retry loop actually retries, in order, then gives up -----


def _exec(fragment: str, extra_globals: dict | None = None) -> dict:
    ns: dict = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    ns.update(extra_globals or {})
    exec(compile(fragment, "<fragment>", "exec"), ns)
    return ns


def test_succeeds_on_a_later_attempt_without_ever_reaching_breakpoint():
    fragment = (
        "_calls.append(1)\n"
        "if len(_calls) < 3:\n"
        "    raise ValueError('not yet')\n"
        "_ok = True"
    )
    wrapped = _wrap_with_retry(fragment, None, "n1", "N", max_attempts=3, retry_delay_seconds=0)
    ns = _exec(wrapped, {"_calls": []})
    assert len(ns["_calls"]) == 3
    assert ns["_ok"] is True


def test_gives_up_after_exhausting_attempts_and_never_raises_out(monkeypatch):
    # breakpoint() calls sys.breakpointhook() under the hood — stub THAT (not
    # builtins.breakpoint, which pdb's own machinery ends up bypassing) so
    # exhausting every attempt is observable in a test without actually pausing.
    monkeypatch.setattr(sys, "breakpointhook", lambda *a, **k: None)
    fragment = "_calls.append(1)\nraise ValueError('always fails')"
    wrapped = _wrap_with_retry(fragment, None, "n1", "N", max_attempts=3, retry_delay_seconds=0)
    ns = _exec(wrapped, {"_calls": []})
    assert len(ns["_calls"]) == 3  # tried exactly max_attempts times, no more


def test_result_capture_only_runs_after_a_successful_attempt():
    fragment = "_calls.append(1)\nif len(_calls) < 2:\n    raise ValueError('not yet')\nresultVar = 'done'"
    capture = 'print("__NODE_RESULT__" + json.dumps({"nodeId": \'n1\', "key": \'resultVar\', "value": resultVar}, default=str))'
    wrapped = _wrap_with_retry(fragment, capture, "n1", "N", max_attempts=3, retry_delay_seconds=0)
    ns = _exec(wrapped, {"_calls": []})
    assert ns["resultVar"] == "done"


def test_sleeps_between_failed_attempts(monkeypatch):
    slept = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    fragment = "_calls.append(1)\nif len(_calls) < 3:\n    raise ValueError('not yet')"
    wrapped = _wrap_with_retry(fragment, None, "n1", "N", max_attempts=3, retry_delay_seconds=0.5)
    _exec(wrapped, {"_calls": []})
    assert slept == [0.5, 0.5]  # once after each of the 2 failed attempts, not after the 3rd (successful) one


# --- generate_script integration: WFNode.maxAttempts/retryDelaySeconds wire through


def test_generate_script_uses_maxattempts_from_the_node():
    nodes = [WFNode(id="n1", type="click", position=Position(x=0, y=0), params={"selector": "#x"}, maxAttempts=3)]
    script = generate_script(nodes, [], "p", workflow_id="w")
    compile(script, "<generated>", "exec")
    assert "for _attempt in range(1, 4):" in script


def test_generate_script_default_maxattempts_is_unchanged_single_try():
    nodes = [WFNode(id="n1", type="click", position=Position(x=0, y=0), params={"selector": "#x"})]
    script = generate_script(nodes, [], "p", workflow_id="w")
    compile(script, "<generated>", "exec")
    assert "for _attempt in range(" not in script
    assert script.count("except Exception as _e:") == 1


def test_generate_script_ignores_retries_on_a_non_retryable_node_type():
    # Pause isn't wrapped at all (it calls breakpoint() itself) — maxAttempts has
    # nothing to attach to, and must not break codegen.
    nodes = [WFNode(id="n1", type="pause", position=Position(x=0, y=0), params={}, maxAttempts=4)]
    script = generate_script(nodes, [], "p", workflow_id="w")
    compile(script, "<generated>", "exec")
    assert "for _attempt in range(" not in script
