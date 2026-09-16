"""Tests for the Error node (backend/app/nodes/error.py) — deliberately fails a run
right where it's placed, printing __WORKFLOW_MARK_ERROR__ (parsed by
app/execution/runner.py's _stream_output, see test_runner_unattended_error.py for the
unpublish-on-marker behavior) then raising, so the engine's own try/except wrap around
it (see app/codegen/engine.py) catches it like any other node failure.
"""

import json

import pytest

from app.codegen.context import CodegenContext
from app.codegen.engine import HEADER, generate_script
from app.models.workflow import Position, WFEdge, WFNode
from app.nodes.error import codegen_error
from app.nodes.registry import NODE_REGISTRY


def _ctx(params: dict) -> CodegenContext:
    return CodegenContext(node_id="n1", params=params, in_loop=False, target_var="page", node_label="Error")


def test_node_registered_with_expected_shape():
    spec = NODE_REGISTRY["error"]
    assert spec.label == "Error"
    assert spec.category == "logic"
    assert spec.icon == "octagon-alert"
    param_keys = {p.key for p in spec.params}
    assert "message" in param_keys


def test_codegen_default_message_when_none_given():
    fragment = codegen_error(_ctx({}))
    lines = fragment.splitlines()
    assert lines[0].startswith('print("__WORKFLOW_MARK_ERROR__"')
    assert "Error node reached" in lines[0]
    assert lines[1] == "raise RuntimeError('Error node reached')"


def test_codegen_uses_custom_message():
    fragment = codegen_error(_ctx({"message": "Unexpected account status"}))
    lines = fragment.splitlines()
    assert "Unexpected account status" in lines[0]
    assert lines[1] == "raise RuntimeError('Unexpected account status')"


def test_marker_line_is_valid_json_after_the_prefix():
    fragment = codegen_error(_ctx({"message": "boom"}))
    marker_line = fragment.splitlines()[0]
    ns: dict = {"json": json}
    printed = eval(marker_line[len("print(") : -1], ns)  # noqa: S307 - trusted, fixed test fragment
    assert printed.startswith("__WORKFLOW_MARK_ERROR__")
    payload = json.loads(printed[len("__WORKFLOW_MARK_ERROR__") :])
    assert payload == {"nodeId": "n1", "message": "boom"}


def test_executing_the_fragment_raises_with_the_message():
    fragment = codegen_error(_ctx({"message": "boom"}))
    ns: dict = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    with pytest.raises(RuntimeError, match="boom"):
        exec(compile(fragment, "<fragment>", "exec"), ns)


def test_generate_script_wraps_it_like_any_other_failing_node():
    nodes = [WFNode(id="n1", type="error", position=Position(x=0, y=0), params={"message": "boom"})]
    script = generate_script(nodes, [], "p", workflow_id="w")
    compile(script, "<generated>", "exec")
    assert "__WORKFLOW_MARK_ERROR__" in script
    assert "raise RuntimeError('boom')" in script
    assert "__NODE_ERROR__n1" in script
    assert "breakpoint()" in script


def test_supports_template_in_message():
    nodes = [
        WFNode(id="n1", type="error", position=Position(x=0, y=0), params={"message": "bad status: {{status}}"}),
    ]
    script = generate_script(nodes, [], "p", workflow_id="w")
    compile(script, "<generated>", "exec")
    assert 'f"bad status: {status}"' in script
