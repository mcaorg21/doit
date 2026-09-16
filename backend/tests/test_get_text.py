"""Tests for the Get Text node's explicit wait-for-element + configurable Timeout
(backend/app/nodes/get_text.py) — added because an unstable/slow site can delay when
the target element actually renders, and .inner_text() alone doesn't expose its own
wait as a per-node configurable Timeout the way wait_for() does.

Real headless Chromium, same _exec_fragment-against-HEADER pattern as
test_click_bypass.py — exercises the actual codegen'd Python against a real page.
"""

import pytest
from playwright.sync_api import sync_playwright

from app.codegen.context import CodegenContext
from app.codegen.engine import HEADER
from app.nodes.get_text import codegen_get_text
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


def _ctx(params: dict) -> CodegenContext:
    return CodegenContext(node_id="test_node", params=params, in_loop=False, target_var="page", node_label="Get Text")


def _exec_fragment(page, fragment: str) -> dict:
    ns: dict = {}
    exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    exec(compile(fragment, "<fragment>", "exec"), ns)
    return ns


def test_node_registered_with_timeout_param():
    spec = NODE_REGISTRY["get_text"]
    field = next(p for p in spec.params if p.key == "timeout")
    assert field.type == "number"
    assert field.default == 30


def test_codegen_waits_before_reading_with_default_timeout():
    fragment = codegen_get_text(_ctx({"selector": "#price", "selectorType": "css", "resultVar": "price"}))
    lines = fragment.splitlines()
    assert lines[0] == "page.locator('#price').wait_for(state='visible', timeout=30000)"
    assert lines[1] == "price = page.locator('#price').inner_text()"


def test_codegen_uses_custom_timeout():
    fragment = codegen_get_text(
        _ctx({"selector": "#price", "selectorType": "css", "resultVar": "price", "timeout": 5})
    )
    assert "wait_for(state='visible', timeout=5000)" in fragment.splitlines()[0]


def test_waits_for_an_element_that_appears_late(page):
    page.set_content("<div></div>")
    page.evaluate(
        "setTimeout(() => { document.querySelector('div').innerHTML = \"<span id='price'>42</span>\" }, 300)"
    )
    fragment = codegen_get_text(_ctx({"selector": "#price", "selectorType": "css", "resultVar": "price", "timeout": 2}))
    ns = _exec_fragment(page, fragment)
    assert ns["price"] == "42"


def test_raises_if_element_never_appears_within_timeout(page):
    page.set_content("<div></div>")
    fragment = codegen_get_text(
        _ctx({"selector": "#missing", "selectorType": "css", "resultVar": "x", "timeout": 0.5})
    )
    with pytest.raises(Exception):
        _exec_fragment(page, fragment)
