"""Tests for the Click node's "Bypass — continue the run even if this click fails"
option (backend/app/nodes/click.py).

Real headless Chromium, same _exec_fragment-against-HEADER pattern as
test_download_file.py/test_cookies.py — this exercises the actual codegen'd Python,
not a mock of it. page.set_default_timeout() is lowered before exec'ing a fragment
against a missing selector so these don't wait out Playwright's real 30s default.
"""

import pytest
from playwright.sync_api import sync_playwright

from app.codegen.context import CodegenContext
from app.codegen.engine import HEADER, generate_script
from app.models.workflow import Position, WFEdge, WFNode
from app.nodes.click import codegen_click
from app.nodes.registry import NODE_REGISTRY

PROJECT_ID = "__test_click_bypass_project__"
WORKFLOW_ID = "__test_click_bypass_workflow__"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    pg = browser.new_page()
    pg.set_default_timeout(500)
    pg.set_content('<button id="real">click me</button>')
    yield pg
    pg.close()


def _ctx(params: dict) -> CodegenContext:
    return CodegenContext(node_id="test_node", params=params, in_loop=False, target_var="page", node_label="Click")


def _exec_fragment(page, fragment: str) -> dict:
    ns: dict = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    exec(compile(fragment, "<fragment>", "exec"), ns)
    return ns


def test_node_registered_with_bypass_param():
    spec = NODE_REGISTRY["click"]
    param_keys = {p.key for p in spec.params}
    assert "bypassOnFailure" in param_keys
    field = next(p for p in spec.params if p.key == "bypassOnFailure")
    assert field.type == "boolean"
    assert field.default is False


def test_node_registered_with_timeout_param():
    spec = NODE_REGISTRY["click"]
    field = next(p for p in spec.params if p.key == "timeout")
    assert field.type == "number"
    assert field.default == 30


def test_custom_timeout_is_converted_to_milliseconds():
    fragment = codegen_click(_ctx({"selector": "#real", "selectorType": "css", "timeout": 5}))
    assert "page.locator('#real').click(timeout=5000)" in fragment.splitlines()[0]


def test_bypass_off_is_flat_and_still_the_original_two_lines():
    fragment = codegen_click(_ctx({"selector": "#real", "selectorType": "css"}))
    lines = fragment.splitlines()
    assert lines == [
        "page.locator('#real').click(timeout=30000)",
        'print(f"[Click] clicked " + \'#real\')',
    ]
    for line in lines:
        assert not line[:1].isspace()


def test_bypass_off_raises_on_missing_element(page):
    # Explicit timeout param (not just the page's set_default_timeout(500)) since the
    # generated click() now always passes its own timeout= kwarg, which overrides it.
    fragment = codegen_click(_ctx({"selector": "#missing", "selectorType": "css", "timeout": 0.5}))
    with pytest.raises(Exception):
        _exec_fragment(page, fragment)


def test_bypass_on_swallows_failure_and_keeps_going(page):
    fragment = codegen_click(
        _ctx({"selector": "#missing", "selectorType": "css", "bypassOnFailure": True, "timeout": 0.5})
    )
    _exec_fragment(page, fragment)  # must NOT raise


def test_bypass_on_still_clicks_when_element_is_present(page):
    page.evaluate("document.getElementById('real').addEventListener('click', () => { window.__clicked = true })")
    fragment = codegen_click(_ctx({"selector": "#real", "selectorType": "css", "bypassOnFailure": True}))
    _exec_fragment(page, fragment)
    # A real click happened (not silently skipped just because bypass is on).
    assert page.evaluate("window.__clicked") is True


def test_engine_auto_wrap_never_fires_for_a_bypassed_click():
    """The engine wraps every non-block node in its own try/except that breakpoint()s
    on failure (see engine.py render()) — with bypass on, the click's OWN inner
    try/except must swallow the failure first, so the outer wrap's except branch (and
    its breakpoint()) never gets reached at runtime (proven directly by
    test_bypass_on_swallows_failure_and_keeps_going above, which executes the bare
    fragment with no outer wrap and shows it doesn't raise). This test only checks
    the generated script's STRUCTURE: both the inner (bypass) and the outer (engine
    auto-wrap) try/except must be present and correctly nested, not one replacing
    the other."""
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(
            id="n2",
            type="click",
            position=Position(x=1, y=0),
            params={"selector": "#definitely-not-there", "selectorType": "css", "bypassOnFailure": True},
        ),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2")]
    script = generate_script(nodes, edges, PROJECT_ID, workflow_id=WORKFLOW_ID)
    compile(script, "<generated>", "exec")
    assert "except Exception as _e:" in script
    # Both the inner (bypass) and outer (engine auto-wrap) except blocks are present —
    # confirms nesting happened rather than one replacing the other.
    assert script.count("except Exception as _e:") == 2
    assert "breakpoint()" in script
