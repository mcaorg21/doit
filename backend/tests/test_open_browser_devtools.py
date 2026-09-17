"""Tests for Open Browser's Chrome DevTools auto-open (backend/app/nodes/
open_browser.py) — deliberately OFF for every real run generate_script() produces
("Run workflow", a schedule/webhook trigger, MCP run_workflow, ...) even when the
workflow has a Pause node or a breakpoint on a connector, but still ON for a live/
voice-guided build session (app/mcp/live_sessions.py), which explicitly opts in via
CodegenContext.has_breakpoints since a human is already watching that browser to
inspect elements between MCP steps.
"""

from app.codegen.context import CodegenContext
from app.codegen.engine import generate_script
from app.models.workflow import Position, WFEdge, WFNode
from app.nodes.open_browser import codegen_open_browser

DEVTOOLS_FLAG = "--auto-open-devtools-for-tabs"


def _ctx(**overrides) -> CodegenContext:
    params = {"headless": False, "browserChannel": "chrome"}
    params.update(overrides.pop("params", {}))
    return CodegenContext(node_id="n1", params=params, in_loop=False, node_label="Open Browser", **overrides)


def test_default_context_never_opens_devtools():
    fragment = codegen_open_browser(_ctx())
    assert DEVTOOLS_FLAG not in fragment


def test_explicit_has_breakpoints_still_opens_devtools_for_a_live_session():
    fragment = codegen_open_browser(_ctx(has_breakpoints=True))
    assert DEVTOOLS_FLAG in fragment


def test_has_breakpoints_still_respects_headless_and_chromium_guards():
    assert DEVTOOLS_FLAG not in codegen_open_browser(_ctx(has_breakpoints=True, params={"headless": True}))
    assert DEVTOOLS_FLAG not in codegen_open_browser(_ctx(has_breakpoints=True, params={"browserChannel": "chromium"}))


def test_generate_script_never_opens_devtools_even_with_a_pause_node():
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": False}),
        WFNode(id="n2", type="pause", position=Position(x=1, y=0), params={}),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2")]
    script = generate_script(nodes, edges, "p", workflow_id="w")
    compile(script, "<generated>", "exec")
    assert DEVTOOLS_FLAG not in script


def test_generate_script_never_opens_devtools_even_with_a_breakpoint_edge():
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": False}),
        WFNode(id="n2", type="close_browser", position=Position(x=1, y=0), params={}),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2", breakpoint=True)]
    script = generate_script(nodes, edges, "p", workflow_id="w")
    compile(script, "<generated>", "exec")
    assert DEVTOOLS_FLAG not in script
