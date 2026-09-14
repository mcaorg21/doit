"""Tests for the generic per-node result-capture marker
(app/codegen/engine.py::_result_capture_lines and its wiring into generate_script) —
the mechanism behind every producesVariable field's example getting refreshed on
every real Run, without each node type's own codegen needing to know about it.
"""

from app.codegen.engine import _result_capture_lines, generate_script
from app.models.workflow import Position, WFEdge, WFNode
from app.nodes.base import NodeSpec, ParamField

PROJECT_ID = "__test_engine_result_capture_project__"
WORKFLOW_ID = "__test_engine_result_capture_workflow__"


def _spec(**param_kwargs) -> NodeSpec:
    return NodeSpec(
        type="fake",
        label="Fake",
        category="action",
        description="",
        params=[ParamField(**param_kwargs)],
        codegen=lambda ctx: "pass",
    )


def test_no_marker_when_no_producesvariable_param():
    node = WFNode(id="n1", type="fake", position=Position(x=0, y=0), params={"resultVar": "x"})
    spec = _spec(key="resultVar", label="Result Variable", type="text")  # producesVariable defaults False
    assert _result_capture_lines(node, spec) is None


def test_no_marker_when_field_left_blank():
    node = WFNode(id="n1", type="fake", position=Position(x=0, y=0), params={})
    spec = _spec(key="resultVar", label="Result Variable", type="text", producesVariable=True)
    assert _result_capture_lines(node, spec) is None


def test_marker_line_shape_for_a_filled_in_field():
    node = WFNode(id="n1", type="fake", position=Position(x=0, y=0), params={"resultVar": "price"})
    spec = _spec(key="resultVar", label="Result Variable", type="text", producesVariable=True)
    line = _result_capture_lines(node, spec)
    assert line == '''print("__NODE_RESULT__" + json.dumps({"nodeId": 'n1', "key": 'resultVar', "value": price}, default=str))'''


def test_get_text_in_a_real_graph_emits_a_compilable_marker():
    """End-to-end through generate_script (not just the isolated helper) for a real
    node type (get_text), proving the marker lands inside the try body — after the
    assignment, so the variable always exists by the time it's referenced — and the
    whole script still compiles."""
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(
            id="n2",
            type="get_text",
            position=Position(x=1, y=0),
            params={"selector": "#price", "selectorType": "css", "resultVar": "price"},
        ),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2")]
    script = generate_script(nodes, edges, PROJECT_ID, workflow_id=WORKFLOW_ID)

    marker_line = '''print("__NODE_RESULT__" + json.dumps({"nodeId": 'n2', "key": 'resultVar', "value": price}, default=str))'''
    assert marker_line in script

    assignment_index = script.index("price = page.locator")
    marker_index = script.index(marker_line)
    assert assignment_index < marker_index  # marker always comes after the assignment it depends on

    compile(script, "<generated>", "exec")


def test_marker_omitted_entirely_during_preview_generation():
    """A preview script exits right after its target node (see generate_script's
    preview_node_id/preview_var) — the result-capture marker would be redundant
    noise there (and could even reference a variable before it's fully settled for a
    node that opens a block), so it's skipped whenever preview_node_id is set."""
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(
            id="n2",
            type="get_text",
            position=Position(x=1, y=0),
            params={"selector": "#price", "selectorType": "css", "resultVar": "price"},
        ),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2")]
    script = generate_script(
        nodes, edges, PROJECT_ID, workflow_id=WORKFLOW_ID, preview_node_id="n2", preview_var="price"
    )
    assert "__NODE_RESULT__" not in script
    assert "__PREVIEW__" in script
