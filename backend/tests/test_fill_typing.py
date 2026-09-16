"""Tests for the Fill Input node's "Clear the field first" / "Simulate typing" options
(backend/app/nodes/fill.py).

Real headless Chromium, same _exec_fragment-against-HEADER pattern as
test_click_bypass.py — exercises the actual codegen'd Python against a real page, not
a mock of it.
"""

import pytest
from playwright.sync_api import sync_playwright

from app.codegen.context import CodegenContext
from app.codegen.engine import HEADER
from app.nodes.fill import codegen_fill
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
    pg.set_content(
        """
        <input id="target" value="old" />
        <script>
          window.__inputEvents = 0;
          document.getElementById('target').addEventListener('input', () => { window.__inputEvents++; });
        </script>
        """
    )
    yield pg
    pg.close()


def _ctx(params: dict) -> CodegenContext:
    return CodegenContext(node_id="test_node", params=params, in_loop=False, target_var="page", node_label="Fill")


def _exec_fragment(page, fragment: str) -> dict:
    ns: dict = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    exec(compile(fragment, "<fragment>", "exec"), ns)
    return ns


def test_node_registered_with_new_params():
    spec = NODE_REGISTRY["fill"]
    param_keys = {p.key for p in spec.params}
    assert "clearFirst" in param_keys
    assert "simulateTyping" in param_keys
    for key in ("clearFirst", "simulateTyping"):
        field = next(p for p in spec.params if p.key == key)
        assert field.type == "boolean"
        assert field.default is False


def test_default_is_unchanged_single_line_fill():
    fragment = codegen_fill(_ctx({"selector": "#target", "selectorType": "css", "value": "hi"}))
    lines = fragment.splitlines()
    assert lines == [
        "page.locator('#target').fill('hi')",
        'print(f"[Fill] filled " + \'#target\')',
    ]


def test_clear_first_emits_clear_before_fill():
    fragment = codegen_fill(_ctx({"selector": "#target", "selectorType": "css", "value": "hi", "clearFirst": True}))
    lines = fragment.splitlines()
    assert lines[0] == "page.locator('#target').clear()"
    assert lines[1] == "page.locator('#target').fill('hi')"


def test_simulate_typing_uses_press_sequentially():
    fragment = codegen_fill(_ctx({"selector": "#target", "selectorType": "css", "value": "hi", "simulateTyping": True}))
    lines = fragment.splitlines()
    assert lines[0] == "page.locator('#target').press_sequentially('hi')"


def test_both_options_clear_then_simulate_typing():
    fragment = codegen_fill(
        _ctx({"selector": "#target", "selectorType": "css", "value": "hi", "clearFirst": True, "simulateTyping": True})
    )
    lines = fragment.splitlines()
    assert lines[0] == "page.locator('#target').clear()"
    assert lines[1] == "page.locator('#target').press_sequentially('hi')"


def test_clear_first_actually_empties_a_prefilled_field(page):
    fragment = codegen_fill(_ctx({"selector": "#target", "selectorType": "css", "value": "new", "clearFirst": True}))
    _exec_fragment(page, fragment)
    assert page.eval_on_selector("#target", "el => el.value") == "new"


def test_simulate_typing_fires_one_input_event_per_character(page):
    fragment = codegen_fill(_ctx({"selector": "#target", "selectorType": "css", "value": "abc", "simulateTyping": True}))
    _exec_fragment(page, fragment)
    # press_sequentially dispatches real key events — one 'input' event per character —
    # unlike .fill(), which sets the value directly and fires a single input event.
    assert page.evaluate("window.__inputEvents") == len("abc")


def test_plain_fill_fires_a_single_input_event(page):
    fragment = codegen_fill(_ctx({"selector": "#target", "selectorType": "css", "value": "abc"}))
    _exec_fragment(page, fragment)
    assert page.evaluate("window.__inputEvents") == 1
