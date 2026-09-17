"""Tests for the "Element Condition" node (backend/app/nodes/element_if.py) — the
fusion of Element Present? and IF the user asked for: look for an element and, only
if it's there, evaluate a condition on it (its text or one attribute) in the same
step, branching true/false like the IF node does.

Real headless Chromium, same _exec_fragment-against-HEADER pattern as
test_get_text.py — exercises the actual codegen'd Python against a real page.
"""

import pytest
from playwright.sync_api import sync_playwright

from app.codegen.context import CodegenContext, CodegenError
from app.codegen.engine import HEADER, generate_script
from app.models.workflow import Position, WFEdge, WFNode
from app.nodes.element_if import codegen_element_if
from app.nodes.registry import NODE_REGISTRY


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    pg = browser.new_page()
    yield pg
    pg.close()


def _ctx(params: dict, node_id: str = "n1") -> CodegenContext:
    return CodegenContext(node_id=node_id, params=params, in_loop=False, target_var="page", node_label="Element Condition")


def _exec_branch(page, fragment: str) -> dict:
    """Runs a codegen_element_if fragment (which ends in an open `if ...:` with no
    body) against a real page, recording which branch was taken as ns['_branch']."""
    ns: dict = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    script = fragment + "\n    _branch = True\nelse:\n    _branch = False"
    exec(compile(script, "<fragment>", "exec"), ns)
    return ns


# --- Registration ------------------------------------------------------------


def test_node_registered_as_branch_that_opens_a_block():
    spec = NODE_REGISTRY["element_if"]
    assert spec.is_branch is True
    assert spec.opens_block is True
    assert spec.category == "logic"


def test_not_retryable_like_other_branch_nodes():
    assert NODE_REGISTRY["element_if"].to_public_dict()["retryable"] is False


# --- Presence-only mode --------------------------------------------------------


def test_presence_mode_true_when_element_exists(page):
    page.set_content("<div id='badge'>ok</div>")
    fragment = codegen_element_if(_ctx({"selector": "#badge", "selectorType": "css", "checkMode": "presence"}))
    ns = _exec_branch(page, fragment)
    assert ns["_branch"] is True


def test_presence_mode_false_when_element_missing(page):
    page.set_content("<div></div>")
    fragment = codegen_element_if(
        _ctx({"selector": "#badge", "selectorType": "css", "checkMode": "presence", "timeout": 0.3})
    )
    ns = _exec_branch(page, fragment)
    assert ns["_branch"] is False


def test_presence_mode_waits_for_an_element_that_appears_late(page):
    page.set_content("<div></div>")
    page.evaluate(
        "setTimeout(() => { document.querySelector('div').innerHTML = \"<span id='badge'>hi</span>\" }, 300)"
    )
    fragment = codegen_element_if(
        _ctx({"selector": "#badge", "selectorType": "css", "checkMode": "presence", "timeout": 2})
    )
    ns = _exec_branch(page, fragment)
    assert ns["_branch"] is True


def test_presence_mode_stores_result_var(page):
    page.set_content("<div id='badge'>ok</div>")
    fragment = codegen_element_if(
        _ctx({"selector": "#badge", "selectorType": "css", "checkMode": "presence", "resultVar": "found"})
    )
    ns = _exec_branch(page, fragment)
    assert ns["found"] is True


# --- Text mode -----------------------------------------------------------------


def test_text_mode_contains_matches(page):
    page.set_content("<div id='status'>Status: Aprovado</div>")
    fragment = codegen_element_if(
        _ctx(
            {
                "selector": "#status",
                "selectorType": "css",
                "checkMode": "text",
                "operator": "contains",
                "value": "Aprovado",
            }
        )
    )
    ns = _exec_branch(page, fragment)
    assert ns["_branch"] is True


def test_text_mode_equal_does_not_match(page):
    page.set_content("<div id='status'>Status: Aprovado</div>")
    fragment = codegen_element_if(
        _ctx(
            {
                "selector": "#status",
                "selectorType": "css",
                "checkMode": "text",
                "operator": "equal",
                "value": "Aprovado",
            }
        )
    )
    ns = _exec_branch(page, fragment)
    assert ns["_branch"] is False  # inner_text is "Status: Aprovado", not exactly "Aprovado"


def test_text_mode_false_when_element_absent_never_raises(page):
    page.set_content("<div></div>")
    fragment = codegen_element_if(
        _ctx(
            {
                "selector": "#missing",
                "selectorType": "css",
                "checkMode": "text",
                "operator": "contains",
                "value": "anything",
                "timeout": 0.3,
            }
        )
    )
    ns = _exec_branch(page, fragment)
    assert ns["_branch"] is False


def test_text_mode_stores_result_var(page):
    page.set_content("<div id='status'>Aprovado</div>")
    fragment = codegen_element_if(
        _ctx(
            {
                "selector": "#status",
                "selectorType": "css",
                "checkMode": "text",
                "operator": "contains",
                "value": "Apr",
                "resultVar": "statusText",
            }
        )
    )
    ns = _exec_branch(page, fragment)
    assert ns["statusText"] == "Aprovado"


def test_text_mode_empty_operator_needs_no_value(page):
    page.set_content("<div id='status'></div>")
    fragment = codegen_element_if(
        _ctx({"selector": "#status", "selectorType": "css", "checkMode": "text", "operator": "empty"})
    )
    ns = _exec_branch(page, fragment)
    assert ns["_branch"] is True


# --- Attribute mode --------------------------------------------------------------


def test_attribute_mode_equal_matches(page):
    page.set_content("<div id='row' data-status='paid'></div>")
    fragment = codegen_element_if(
        _ctx(
            {
                "selector": "#row",
                "selectorType": "css",
                "checkMode": "attribute",
                "attributeName": "data-status",
                "operator": "equal",
                "value": "paid",
            }
        )
    )
    ns = _exec_branch(page, fragment)
    assert ns["_branch"] is True


def test_attribute_mode_requires_attribute_name():
    with pytest.raises(CodegenError):
        codegen_element_if(
            _ctx(
                {
                    "selector": "#row",
                    "selectorType": "css",
                    "checkMode": "attribute",
                    "operator": "equal",
                    "value": "paid",
                }
            )
        )


# --- Full generate_script wiring: true/false branches nest correctly -------------


def test_generate_script_compiles_with_result_var_on_a_branch_node():
    # Regression test: engine.py's generic __NODE_RESULT__ capture (for any
    # producesVariable field) used to be appended straight after a block-opening
    # fragment, landing right after Element Condition's "if ...:" header at the same
    # indent — an IndentationError. The IF node never has a producesVariable field, so
    # this never surfaced until Element Condition's optional "resultVar" did.
    nodes = [
        WFNode(
            id="n1",
            type="element_if",
            position=Position(x=0, y=0),
            params={"selector": "#x", "checkMode": "presence", "resultVar": "found"},
        ),
        WFNode(id="n2", type="click", position=Position(x=0, y=1), params={"selector": "#yes"}),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2", sourceHandle="true")]
    script = generate_script(nodes, edges, "p", workflow_id="w")
    compile(script, "<generated>", "exec")
    assert '"nodeId": \'n1\'' in script
    assert "if _present_n1:" in script


def test_generate_script_nests_true_and_false_branches():
    nodes = [
        WFNode(id="n1", type="element_if", position=Position(x=0, y=0), params={"selector": "#x", "checkMode": "presence"}),
        WFNode(id="n2", type="click", position=Position(x=0, y=1), params={"selector": "#yes"}),
        WFNode(id="n3", type="click", position=Position(x=0, y=2), params={"selector": "#no"}),
    ]
    edges = [
        WFEdge(id="e1", source="n1", target="n2", sourceHandle="true"),
        WFEdge(id="e2", source="n1", target="n3", sourceHandle="false"),
    ]
    script = generate_script(nodes, edges, "p", workflow_id="w")
    compile(script, "<generated>", "exec")
    assert "if _present_n1:" in script
    assert "else:" in script
    assert "#yes" in script and "#no" in script
