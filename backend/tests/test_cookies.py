"""Tests for the save_cookies/load_cookies nodes (backend/app/nodes/save_cookies.py,
backend/app/nodes/load_cookies.py).

Fragments run via exec() against the same HEADER text generate_script prepends to
every real generated script (see test_download_file.py for the established pattern),
against a real (headless) Chromium page — so this exercises the actual codegen'd
Python and real Playwright cookie APIs, not a mock of either.
"""

import json
import shutil

import pytest
from playwright.sync_api import sync_playwright

from app.codegen.context import CodegenContext
from app.codegen.engine import HEADER, generate_script
from app.config import cookies_dir
from app.models.workflow import Position, WFEdge, WFNode
from app.nodes.load_cookies import codegen_load_cookies
from app.nodes.registry import NODE_REGISTRY
from app.nodes.save_cookies import codegen_save_cookies

PROJECT_ID = "__test_cookies_project__"
WORKFLOW_ID = "__test_cookies_workflow__"


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


@pytest.fixture(autouse=True)
def clean_cookies_dir():
    d = cookies_dir(PROJECT_ID, WORKFLOW_ID)
    if d.exists():
        shutil.rmtree(d)
    yield d
    if d.exists():
        shutil.rmtree(d)


def _ctx(params: dict, node_label: str = "Cookies") -> CodegenContext:
    return CodegenContext(
        node_id="test_node",
        params=params,
        in_loop=False,
        project_id=PROJECT_ID,
        workflow_id=WORKFLOW_ID,
        target_var="page",
        node_label=node_label,
    )


def _exec_fragment(page, fragment: str, ns: dict | None = None) -> dict:
    if ns is None:
        ns = {}
        exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    exec(compile(fragment, "<fragment>", "exec"), ns)
    return ns


_A_COOKIE = {
    "name": "session_id",
    "value": "abc123",
    "domain": "example.com",
    "path": "/",
}


# --- catalog / registry ---------------------------------------------------


def test_nodes_registered_with_expected_shape():
    for node_type, label in (("save_cookies", "Save Cookies"), ("load_cookies", "Load Cookies")):
        assert node_type in NODE_REGISTRY
        spec = NODE_REGISTRY[node_type]
        assert spec.label == label
        assert spec.category == "browser"
        assert spec.icon == "cookie"
        assert spec.opens_block is False
        assert spec.is_branch is False


def test_get_node_catalog_includes_both():
    from app.services.workflow_reconstructor import build_node_catalog

    catalog = build_node_catalog()
    types = {c["type"] for c in catalog}
    assert {"save_cookies", "load_cookies"} <= types


def test_validate_workflow_accepts_open_browser_save_and_load_cookies():
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(id="n2", type="load_cookies", position=Position(x=1, y=0), params={}),
        WFNode(id="n3", type="save_cookies", position=Position(x=2, y=0), params={}),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2"), WFEdge(id="e2", source="n2", target="n3")]
    script = generate_script(nodes, edges, PROJECT_ID, workflow_id=WORKFLOW_ID)
    compile(script, "<generated>", "exec")


# --- real functional behavior ----------------------------------------------


def test_save_cookies_writes_json_file(page, clean_cookies_dir):
    page.goto("https://example.com")
    page.context.add_cookies([_A_COOKIE])

    fragment = codegen_save_cookies(_ctx({"filename": "sess.json"}))
    _exec_fragment(page, fragment)

    path = clean_cookies_dir / "sess.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert any(c["name"] == "session_id" and c["value"] == "abc123" for c in data)


def test_save_cookies_result_var_shape(page):
    page.goto("https://example.com")
    page.context.add_cookies([_A_COOKIE])

    fragment = codegen_save_cookies(_ctx({"filename": "sess.json", "resultVar": "saved"}))
    ns = _exec_fragment(page, fragment)
    assert ns["saved"]["count"] == len(page.context.cookies())
    assert ns["saved"]["path"].endswith("sess.json")


def test_load_cookies_restores_cookie_into_fresh_context(browser, page, clean_cookies_dir):
    # Save from one page/context...
    page.goto("https://example.com")
    page.context.add_cookies([_A_COOKIE])
    save_fragment = codegen_save_cookies(_ctx({"filename": "sess.json"}))
    _exec_fragment(page, save_fragment)

    # ...load into a totally fresh page/context that never had the cookie.
    fresh_page = browser.new_page()
    try:
        fresh_page.goto("https://example.com")
        assert not any(c["name"] == "session_id" for c in fresh_page.context.cookies())

        load_fragment = codegen_load_cookies(_ctx({"filename": "sess.json"}))
        _exec_fragment(fresh_page, load_fragment)

        restored = fresh_page.context.cookies()
        assert any(c["name"] == "session_id" and c["value"] == "abc123" for c in restored)
    finally:
        fresh_page.close()


def test_load_cookies_skips_missing_file_by_default(page, clean_cookies_dir):
    page.goto("https://example.com")
    fragment = codegen_load_cookies(_ctx({"filename": "does-not-exist.json", "resultVar": "loaded"}))
    ns = _exec_fragment(page, fragment)
    assert ns["loaded"] == {"path": str(clean_cookies_dir / "does-not-exist.json"), "count": 0, "loaded": False}


def test_load_cookies_raises_when_skip_if_missing_is_off(page, clean_cookies_dir):
    page.goto("https://example.com")
    fragment = codegen_load_cookies(_ctx({"filename": "does-not-exist.json", "skipIfMissing": False}))
    with pytest.raises(FileNotFoundError):
        _exec_fragment(page, fragment)


def test_save_then_load_in_same_namespace_chain(page, clean_cookies_dir):
    """Two consecutive nodes in the same run, mirroring how they'd actually appear
    back-to-back in a real generated script (chained in one exec namespace)."""
    page.goto("https://example.com")
    page.context.add_cookies([_A_COOKIE, {"name": "theme", "value": "dark", "domain": "example.com", "path": "/"}])

    save_fragment = codegen_save_cookies(_ctx({"filename": "sess.json", "resultVar": "saved"}))
    ns = _exec_fragment(page, save_fragment)
    assert ns["saved"]["count"] == 2

    # Clear cookies, then load them back in the SAME page/context.
    page.context.clear_cookies()
    assert page.context.cookies() == []

    load_fragment = codegen_load_cookies(_ctx({"filename": "sess.json", "resultVar": "loaded"}))
    ns = _exec_fragment(page, load_fragment, ns)
    assert ns["loaded"]["count"] == 2
    names = {c["name"] for c in page.context.cookies()}
    assert names == {"session_id", "theme"}
