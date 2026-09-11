"""Tests for the download_file node (backend/app/nodes/download_file.py).

No test suite existed in this repo before this file — see backend/requirements.txt
for the new pytest dependency, and `cd backend && .venv/Scripts/python.exe -m pytest`
to run it (or `-m pytest tests/test_download_file.py -v` for just this file).

Real downloads are driven against a real (headless) Chromium via Playwright, using a
`data:` URI link with a `download` attribute — confirmed empirically to trigger a real
Playwright download event (page.expect_download), so these exercise the actual
codegen'd Python, not a mock of it. Fragments run via exec() against the same HEADER
text generate_script prepends to every real generated script (so _safe_download_filename/
_unique_download_path/os/base64/etc. are available exactly as they are at runtime),
rather than spinning up a whole subprocess per test.
"""

import base64
import os
import shutil

import pytest
from playwright.sync_api import sync_playwright

from app.codegen.context import CodegenContext
from app.codegen.engine import HEADER, generate_script
from app.config import temp_files_dir
from app.models.workflow import Position, WFEdge, WFNode
from app.nodes.download_file import codegen_download_file, demo_codegen_download_file
from app.nodes.registry import NODE_REGISTRY

PROJECT_ID = "__test_download_file_project__"
WORKFLOW_ID = "__test_download_file_workflow__"


def _link_html(filename: str, content: bytes = b"test content", link_id: str = "dl") -> str:
    b64 = base64.b64encode(content).decode()
    return f'<a id="{link_id}" href="data:application/octet-stream;base64,{b64}" download="{filename}">Download</a>'


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
def clean_temp_dir():
    """This workflow's temp_files dir must not exist before a test starts (several
    tests assert it gets created automatically) and is removed after, so tests don't
    leak files into each other or into the real data/ directory long-term."""
    d = temp_files_dir(PROJECT_ID, WORKFLOW_ID)
    if d.exists():
        shutil.rmtree(d)
    yield d
    if d.exists():
        shutil.rmtree(d)


def _ctx(params: dict, target_var: str = "page") -> CodegenContext:
    return CodegenContext(
        node_id="test_node",
        params=params,
        in_loop=False,
        project_id=PROJECT_ID,
        workflow_id=WORKFLOW_ID,
        target_var=target_var,
        node_label="Download File",
    )


def _exec_fragment(page, fragment: str, ns: dict | None = None) -> dict:
    """Runs a codegen fragment against a real page in a namespace pre-loaded with the
    same runtime helpers (_safe_download_filename, os, base64, ...) HEADER provides to
    every real generated script. Pass an existing `ns` back in to chain a second
    fragment in the same namespace (see test_two_consecutive_download_file_nodes)."""
    if ns is None:
        ns = {}
        exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    exec(compile(fragment, "<fragment>", "exec"), ns)
    return ns


# --- catalog / registry ---------------------------------------------------


def test_node_registered_with_expected_shape():
    assert "download_file" in NODE_REGISTRY
    spec = NODE_REGISTRY["download_file"]
    assert spec.label == "Download File"
    assert spec.category == "action"
    assert spec.icon == "download"
    assert spec.opens_block is False
    assert spec.is_branch is False
    assert spec.demo_codegen is not None
    param_keys = {p.key for p in spec.params}
    assert {"selector", "selectorType", "filename", "timeout", "overwrite", "resultVar"} <= param_keys


def test_get_node_catalog_includes_download_file():
    from app.services.workflow_reconstructor import build_node_catalog

    catalog = build_node_catalog()
    types = {c["type"] for c in catalog}
    assert "download_file" in types
    entry = next(c for c in catalog if c["type"] == "download_file")
    assert entry["category"] == "action"
    assert entry["icon"] == "download"


def test_validate_workflow_accepts_open_browser_goto_download_file():
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(id="n2", type="goto", position=Position(x=1, y=0), params={"url": "https://example.com"}),
        WFNode(
            id="n3",
            type="download_file",
            position=Position(x=2, y=0),
            params={"selector": "#dl", "selectorType": "css"},
        ),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2"), WFEdge(id="e2", source="n2", target="n3")]
    script = generate_script(nodes, edges, PROJECT_ID, workflow_id=WORKFLOW_ID)
    compile(script, "<generated>", "exec")  # raises SyntaxError if generate_script produced something broken


# --- demo-mode safety ------------------------------------------------------


def test_demo_codegen_is_flat():
    """The whole reason demo_codegen exists: every line must be independently
    sendable to a paused pdb prompt one at a time — see app/mcp/live_sessions.py."""
    fragment = demo_codegen_download_file(_ctx({"selector": "#dl", "selectorType": "css", "resultVar": "r"}))
    for line in fragment.splitlines():
        assert not line[:1].isspace(), f"demo_codegen produced an indented line: {line!r}"


def test_normal_codegen_uses_with_block():
    fragment = codegen_download_file(_ctx({"selector": "#dl", "selectorType": "css"}))
    assert "with page.expect_download(" in fragment
    assert "download_info.value" in fragment


def test_demo_codegen_produces_same_result_as_normal(page):
    """Not just flat — actually functionally equivalent to the with-block version
    against a real download (the __enter__/__exit__ split has to behave the same)."""
    page.set_content(_link_html("demo-variant.txt"))
    fragment = demo_codegen_download_file(_ctx({"selector": "#dl", "selectorType": "css", "resultVar": "r"}))
    ns = _exec_fragment(page, fragment)
    assert ns["r"]["filename"] == "demo-variant.txt"
    assert os.path.exists(ns["r"]["path"])


# --- real downloads ---------------------------------------------------------


def test_download_css_selector(page):
    page.set_content(_link_html("report.pdf"))
    fragment = codegen_download_file(_ctx({"selector": "#dl", "selectorType": "css", "resultVar": "result"}))
    ns = _exec_fragment(page, fragment)
    result = ns["result"]
    assert result["filename"] == "report.pdf"
    assert os.path.basename(result["path"]) == "report.pdf"
    # Under temp_files/<workflow>/<process-id>/ — one extra directory level below the
    # workflow dir (the per-execution isolation subfolder, see HEADER's _PROCESS_ID).
    workflow_dir = str(temp_files_dir(PROJECT_ID, WORKFLOW_ID))
    assert result["path"].startswith(workflow_dir + os.sep)
    process_subdir = os.path.dirname(result["path"])
    assert os.path.dirname(process_subdir) == workflow_dir
    assert process_subdir != workflow_dir
    assert os.path.exists(result["path"])


def test_download_xpath_selector(page):
    page.set_content(_link_html("via-xpath.txt"))
    fragment = codegen_download_file(
        _ctx({"selector": "//a[@id='dl']", "selectorType": "xpath", "resultVar": "result"})
    )
    ns = _exec_fragment(page, fragment)
    assert ns["result"]["filename"] == "via-xpath.txt"
    assert os.path.exists(ns["result"]["path"])


def test_suggested_filename_used_when_filename_param_empty(page):
    page.set_content(_link_html("server-suggested.csv"))
    fragment = codegen_download_file(_ctx({"selector": "#dl", "selectorType": "css", "resultVar": "r"}))
    ns = _exec_fragment(page, fragment)
    assert ns["r"]["suggestedFilename"] == "server-suggested.csv"
    assert ns["r"]["filename"] == "server-suggested.csv"


def test_filename_param_renames(page):
    page.set_content(_link_html("original-name.bin"))
    fragment = codegen_download_file(
        _ctx({"selector": "#dl", "selectorType": "css", "filename": "renamed.bin", "resultVar": "r"})
    )
    ns = _exec_fragment(page, fragment)
    assert ns["r"]["filename"] == "renamed.bin"
    assert ns["r"]["suggestedFilename"] == "original-name.bin"
    assert os.path.exists(ns["r"]["path"])
    assert os.path.basename(ns["r"]["path"]) == "renamed.bin"


def test_concurrent_runs_do_not_collide(browser):
    """The scenario that motivated per-process subfolders in the first place: two
    SEPARATE executions of the same workflow (e.g. two webhook calls firing close
    together) downloading the same filename must land in different places, not race
    to overwrite each other. Two independent pages/namespaces here stand in for two
    independent script processes — each gets its own fresh HEADER exec, hence its own
    _PROCESS_ID, exactly like two real spawned processes would."""
    page_a = browser.new_page()
    page_b = browser.new_page()
    try:
        page_a.set_content(_link_html("concurrent.txt", content=b"run A"))
        page_b.set_content(_link_html("concurrent.txt", content=b"run B"))

        fragment = codegen_download_file(_ctx({"selector": "#dl", "selectorType": "css", "resultVar": "r"}))
        ns_a = _exec_fragment(page_a, fragment)
        ns_b = _exec_fragment(page_b, fragment)

        assert ns_a["r"]["filename"] == "concurrent.txt"
        assert ns_b["r"]["filename"] == "concurrent.txt"  # same name, no forced rename
        assert ns_a["r"]["path"] != ns_b["r"]["path"]  # different processes -> different subfolders
        assert open(ns_a["r"]["path"], "rb").read() == b"run A"
        assert open(ns_b["r"]["path"], "rb").read() == b"run B"  # not clobbered by run A
    finally:
        page_a.close()
        page_b.close()


def test_temp_dir_created_automatically(page):
    d = temp_files_dir(PROJECT_ID, WORKFLOW_ID)
    assert not d.exists()
    page.set_content(_link_html("auto-mkdir.txt"))
    fragment = codegen_download_file(_ctx({"selector": "#dl", "selectorType": "css"}))
    _exec_fragment(page, fragment)
    assert d.is_dir()


def test_two_consecutive_download_file_nodes(page):
    """The scenario the request closes on: two download_file nodes back to back,
    the flow ending right after the second."""
    page.set_content(
        _link_html("first.txt", content=b"first", link_id="dl1")
        + _link_html("second.txt", content=b"second", link_id="dl2")
    )
    frag1 = codegen_download_file(_ctx({"selector": "#dl1", "selectorType": "css", "resultVar": "r1"}))
    ns = _exec_fragment(page, frag1)
    frag2 = codegen_download_file(_ctx({"selector": "#dl2", "selectorType": "css", "resultVar": "r2"}))
    ns = _exec_fragment(page, frag2, ns=ns)

    assert ns["r1"]["filename"] == "first.txt"
    assert ns["r2"]["filename"] == "second.txt"
    assert os.path.exists(ns["r1"]["path"])
    assert os.path.exists(ns["r2"]["path"])


# --- safety: traversal, timeout, non-destructive naming ---------------------


def test_path_traversal_dotdot_rejected(page):
    page.set_content(_link_html("whatever.txt"))
    fragment = codegen_download_file(
        _ctx({"selector": "#dl", "selectorType": "css", "filename": "../../evil.txt"})
    )
    with pytest.raises(Exception, match=r"\.\."):
        _exec_fragment(page, fragment)
    # Nothing should have escaped the workflow's temp_files dir.
    escaped = temp_files_dir(PROJECT_ID, WORKFLOW_ID).parent.parent / "evil.txt"
    assert not escaped.exists()


def test_path_traversal_absolute_path_rejected(page):
    page.set_content(_link_html("whatever.txt"))
    fragment = codegen_download_file(
        _ctx({"selector": "#dl", "selectorType": "css", "filename": "/etc/evil.txt"})
    )
    with pytest.raises(Exception, match="absolute path"):
        _exec_fragment(page, fragment)


def test_timeout_when_no_download_occurs(page):
    page.set_content('<a id="no-dl" href="#">Not a download</a>')
    fragment = codegen_download_file(_ctx({"selector": "#no-dl", "selectorType": "css", "timeout": 1}))
    with pytest.raises(Exception, match=r"(?i)timeout"):
        _exec_fragment(page, fragment)


def test_existing_file_gets_nonconflicting_name(page):
    """Each execution gets its own isolated _PROCESS_ID subfolder now (see HEADER),
    so a real same-name conflict only happens between two downloads in the SAME run —
    simulated here by chaining two download_file fragments in one exec namespace
    (same _PROCESS_ID both times), matching how two such nodes in one actual script
    would share it too."""
    page.set_content(_link_html("dup.txt", content=b"first") + _link_html("dup.txt", content=b"second", link_id="dl2"))
    frag1 = codegen_download_file(_ctx({"selector": "#dl", "selectorType": "css", "resultVar": "r1"}))
    ns = _exec_fragment(page, frag1)
    frag2 = codegen_download_file(_ctx({"selector": "#dl2", "selectorType": "css", "resultVar": "r2"}))
    ns = _exec_fragment(page, frag2, ns=ns)

    assert ns["r1"]["filename"] == "dup.txt"
    assert ns["r2"]["filename"] == "dup (1).txt"
    assert os.path.dirname(ns["r1"]["path"]) == os.path.dirname(ns["r2"]["path"])  # same run's subfolder
    assert open(ns["r1"]["path"], "rb").read() == b"first"  # original untouched by the second download


def test_overwrite_true_replaces_existing_file(page):
    page.set_content(
        _link_html("dup2.txt", content=b"old content") + _link_html("dup2.txt", content=b"new content", link_id="dl2")
    )
    frag1 = codegen_download_file(_ctx({"selector": "#dl", "selectorType": "css", "resultVar": "r1"}))
    ns = _exec_fragment(page, frag1)
    frag2 = codegen_download_file(
        _ctx({"selector": "#dl2", "selectorType": "css", "overwrite": True, "resultVar": "r2"})
    )
    ns = _exec_fragment(page, frag2, ns=ns)

    assert ns["r2"]["filename"] == "dup2.txt"
    assert ns["r1"]["path"] == ns["r2"]["path"]  # overwrite=True reused the same path
    assert open(ns["r2"]["path"], "rb").read() == b"new content"


def test_result_var_shape(page):
    page.set_content(_link_html("shape-check.dat"))
    fragment = codegen_download_file(_ctx({"selector": "#dl", "selectorType": "css", "resultVar": "outcome"}))
    ns = _exec_fragment(page, fragment)
    r = ns["outcome"]
    assert set(r.keys()) == {"path", "filename", "suggestedFilename"}
    assert r["filename"] == "shape-check.dat"
    assert r["suggestedFilename"] == "shape-check.dat"
    assert r["path"].endswith("shape-check.dat")
    assert os.path.isabs(r["path"])
