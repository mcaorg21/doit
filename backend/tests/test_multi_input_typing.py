"""Tests for Multi Input's per-row "Clear the field first" / "Simulate typing" options
(backend/app/nodes/multi_input.py) — same options as the standalone Fill Input node,
but one flag pair per row since each row can be a different kind of field.
"""

import pytest
from playwright.sync_api import sync_playwright

from app.codegen.context import CodegenContext
from app.codegen.engine import HEADER
from app.nodes.multi_input import codegen_multi_input


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
        <input id="a" value="old" />
        <input id="b" />
        <script>
          window.__events = { a: 0, b: 0 };
          document.getElementById('a').addEventListener('input', () => { window.__events.a++; });
          document.getElementById('b').addEventListener('input', () => { window.__events.b++; });
        </script>
        """
    )
    yield pg
    pg.close()


def _ctx(params: dict) -> CodegenContext:
    return CodegenContext(node_id="test_node", params=params, in_loop=False, target_var="page", node_label="Multi Input")


def _exec_fragment(page, fragment: str) -> dict:
    ns: dict = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    exec(compile(fragment, "<fragment>", "exec"), ns)
    return ns


def test_default_row_is_unchanged_plain_fill():
    fragment = codegen_multi_input(_ctx({"fields": [{"selector": "#a", "selectorType": "css", "kind": "text", "value": "x"}]}))
    lines = fragment.splitlines()
    assert lines[0] == "page.locator('#a').fill('x')"


def test_clear_first_and_simulate_typing_per_row():
    fragment = codegen_multi_input(
        _ctx(
            {
                "fields": [
                    {"selector": "#a", "selectorType": "css", "kind": "text", "value": "x", "clearFirst": True},
                    {"selector": "#b", "selectorType": "css", "kind": "text", "value": "y", "simulateTyping": True},
                ]
            }
        )
    )
    lines = fragment.splitlines()
    assert lines[0] == "page.locator('#a').clear()"
    assert lines[1] == "page.locator('#a').fill('x')"
    assert lines[2] == "page.locator('#b').press_sequentially('y')"


def test_select_kind_rows_ignore_typing_options():
    fragment = codegen_multi_input(
        _ctx(
            {
                "fields": [
                    {"selector": "#a", "selectorType": "css", "kind": "select", "value": "x", "clearFirst": True, "simulateTyping": True},
                ]
            }
        )
    )
    lines = fragment.splitlines()
    assert lines[0] == "page.locator('#a').select_option('x')"


def test_live_clear_and_simulate_typing_against_a_real_page(page):
    fragment = codegen_multi_input(
        _ctx(
            {
                "fields": [
                    {"selector": "#a", "selectorType": "css", "kind": "text", "value": "new", "clearFirst": True},
                    {"selector": "#b", "selectorType": "css", "kind": "text", "value": "abc", "simulateTyping": True},
                ]
            }
        )
    )
    _exec_fragment(page, fragment)
    assert page.eval_on_selector("#a", "el => el.value") == "new"
    assert page.eval_on_selector("#b", "el => el.value") == "abc"
    assert page.evaluate("window.__events.b") == len("abc")
