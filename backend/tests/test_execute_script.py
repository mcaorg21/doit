"""Tests for the Execute Script (JS) node (backend/app/nodes/execute_script.py) —
the Playwright equivalent of Selenium/ChromeDriver's execute_script(): runs raw JS
against the page, with passed-in values available as arguments[0], arguments[1], ...
and a `return` becoming the node's result.

Real headless Chromium, same _exec_fragment-against-HEADER pattern as
test_login.py/test_html_list_select.py.
"""

import pytest
from playwright.sync_api import sync_playwright

from app.codegen.context import CodegenContext, CodegenError
from app.codegen.engine import HEADER, generate_script
from app.models.workflow import Position, WFEdge, WFNode
from app.nodes.execute_script import codegen_execute_script
from app.nodes.registry import NODE_REGISTRY

PROJECT_ID = "__test_execute_script_project__"
WORKFLOW_ID = "__test_execute_script_workflow__"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    pg = browser.new_page()
    pg.set_content("<title>Test Page</title><div id='box'>hello</div>")
    yield pg
    pg.close()


def _ctx(params: dict, node_label: str = "RunJS") -> CodegenContext:
    return CodegenContext(node_id="test_node", params=params, in_loop=False, target_var="page", node_label=node_label)


def _exec_fragment(page, fragment: str, ns: dict | None = None) -> dict:
    if ns is None:
        ns = {}
        exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    exec(compile(fragment, "<fragment>", "exec"), ns)
    return ns


# --- catalog / registry ---------------------------------------------------


def test_node_registered_with_expected_shape():
    spec = NODE_REGISTRY["execute_script"]
    assert spec.label == "Execute Script (JS)"
    assert spec.category == "action"
    assert spec.icon == "code"
    assert spec.opens_block is False
    param_keys = {p.key for p in spec.params}
    assert {"script", "args", "resultVar"} <= param_keys


def test_get_node_catalog_includes_it():
    from app.services.workflow_reconstructor import build_node_catalog

    catalog = build_node_catalog()
    entry = next(c for c in catalog if c["type"] == "execute_script")
    assert entry["category"] == "action"
    assert entry["icon"] == "code"


def test_validate_workflow_accepts_open_browser_execute_script():
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(id="n2", type="execute_script", position=Position(x=1, y=0), params={"script": "return 1;"}),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2")]
    script = generate_script(nodes, edges, PROJECT_ID, workflow_id=WORKFLOW_ID)
    compile(script, "<generated>", "exec")


def test_missing_script_raises_codegen_error():
    with pytest.raises(CodegenError, match="Script"):
        codegen_execute_script(_ctx({"script": ""}))


def test_empty_argument_raises_codegen_error():
    with pytest.raises(CodegenError, match="argument #1"):
        codegen_execute_script(_ctx({"script": "return 1;", "args": [""]}))


def test_codegen_is_flat_and_demoable():
    """No indented lines — confirms this is naturally live-demoable via MCP without
    needing a demo_codegen override, same bar as goto/click/fill."""
    fragment = codegen_execute_script(_ctx({"script": "return 1;", "resultVar": "r"}))
    for line in fragment.splitlines():
        assert not line[:1].isspace(), f"unexpectedly indented line: {line!r}"


# --- real functional behavior ----------------------------------------------


def test_script_runs_and_captures_return_value(page):
    fragment = codegen_execute_script(_ctx({"script": "return document.title;", "resultVar": "r"}))
    ns = _exec_fragment(page, fragment)
    assert ns["r"] == "Test Page"


def test_script_without_result_var_does_not_raise(page):
    fragment = codegen_execute_script(_ctx({"script": "document.getElementById('box').textContent = 'changed';"}))
    _exec_fragment(page, fragment)
    assert page.eval_on_selector("#box", "el => el.textContent") == "changed"


def test_literal_arguments_are_passed_as_strings(page):
    fragment = codegen_execute_script(
        _ctx({"script": "return arguments[0] + arguments[1];", "args": ["2", "3"], "resultVar": "r"})
    )
    ns = _exec_fragment(page, fragment)
    assert ns["r"] == "23"  # string concatenation, not 2 + 3 = 5 — proves args are plain JS strings here


def test_full_reference_argument_preserves_real_type(page):
    """A row that is ONLY {{var}} must pass the actual Python value (a dict here),
    not str(the_dict) — proving resolve_variable_operand's raw-expression path is
    actually used instead of always falling through to render_template_expr."""
    fragment = codegen_execute_script(
        _ctx({"script": "return typeof arguments[0] + ':' + arguments[0].name;", "args": ["{{lead}}"], "resultVar": "r"})
    )
    ns: dict = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    ns["lead"] = {"name": "Ana"}
    exec(compile(fragment, "<fragment>", "exec"), ns)
    assert ns["r"] == "object:Ana"


def test_mixed_text_with_variable_is_stringified(page):
    fragment = codegen_execute_script(
        _ctx({"script": "return arguments[0];", "args": ["id-{{n}}"], "resultVar": "r"})
    )
    ns: dict = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    ns["n"] = 42
    exec(compile(fragment, "<fragment>", "exec"), ns)
    assert ns["r"] == "id-42"


def test_script_error_propagates(page):
    fragment = codegen_execute_script(_ctx({"script": "throw new Error('boom');"}))
    with pytest.raises(Exception, match="boom"):
        _exec_fragment(page, fragment)
