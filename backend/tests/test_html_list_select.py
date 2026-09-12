"""Tests for the HTML List Select node (backend/app/nodes/html_list_select.py) — for
custom "fake select" HTML menus (a trigger element that reveals a panel of <li>
items), picked by their visible text rather than a fragile position/index selector.

Real headless Chromium, same _exec_fragment-against-HEADER pattern as
test_login.py/test_click_bypass.py. page.set_default_timeout() is lowered so a
deliberately-missing-option test doesn't wait out Playwright's real 30s default.
"""

import pytest
from playwright.sync_api import Error as PlaywrightError, sync_playwright

from app.codegen.context import CodegenContext, CodegenError
from app.codegen.engine import HEADER, generate_script
from app.models.workflow import Position, WFEdge, WFNode
from app.nodes.html_list_select import codegen_html_list_select
from app.nodes.registry import NODE_REGISTRY

PROJECT_ID = "__test_html_list_select_project__"
WORKFLOW_ID = "__test_html_list_select_workflow__"

MENU_HTML = """
<button id="trigger">Status</button>
<button class="clear">Limpar</button>
<div class="panel" style="display:none">
  <ul>
    <li><span>Pesquisar</span></li>
    <li><span>Pesquisar Avançado</span></li>
    <li><span>Aprovado</span></li>
    <li><span>Reprovado</span></li>
  </ul>
</div>
<script>
document.getElementById('trigger').addEventListener('click', function () {
  document.querySelector('.panel').style.display = 'block';
});
document.querySelector('.clear').addEventListener('click', function () {
  window.__cleared = true;
});
window.__clickLog = [];
document.querySelectorAll('li').forEach(function (li) {
  li.addEventListener('click', function () {
    window.__clickLog.push(li.textContent);
  });
});
</script>
"""

DUPLICATE_TEXT_HTML = """
<button id="trigger">Status</button>
<div class="panel" style="display:none">
  <ul>
    <li><span>Aprovado</span></li>
  </ul>
  <ul class="other">
    <li><span>Aprovado</span></li>
  </ul>
</div>
<script>
document.getElementById('trigger').addEventListener('click', function () {
  document.querySelector('.panel').style.display = 'block';
});
</script>
"""

HIDDEN_DUPLICATE_TEXT_HTML = """
<button id="trigger">Status</button>
<div class="panel" style="display:none">
  <ul><li id="visible-option"><span>Removido</span></li></ul>
</div>
<div style="display:none">
  <ul><li id="hidden-option"><span>Removido</span></li></ul>
</div>
<script>
document.getElementById('trigger').addEventListener('click', function () {
  document.querySelector('.panel').style.display = 'block';
});
window.__clickedOption = null;
document.querySelectorAll('li').forEach(function (li) {
  li.addEventListener('click', function () {
    window.__clickedOption = li.id;
  });
});
</script>
"""

CHECKBOX_HTML = """
<button id="trigger">Status</button>
<div class="panel" style="display:none">
  <label><input type="checkbox" value="Antigo" checked><span>Antigo</span></label>
  <label><input type="checkbox" value="Removido"><span>Removido</span></label>
  <div role="checkbox" aria-checked="true" id="aria-old">Outro antigo</div>
</div>
<script>
document.getElementById('trigger').addEventListener('click', function () {
  document.querySelector('.panel').style.display = 'block';
});
document.getElementById('aria-old').addEventListener('click', function () {
  this.setAttribute('aria-checked', this.getAttribute('aria-checked') === 'true' ? 'false' : 'true');
});
</script>
"""

PRIMEFACES_CHECKBOX_HTML = """
<button id="trigger">Status</button>
<div class="panel" style="display:none">
  <div class="ui-selectcheckboxmenu-header">
    <div class="ui-chkbox"><input id="all" type="checkbox" checked></div>
  </div>
  <div class="ui-chkbox"><input value="Ativo" type="checkbox" checked></div><span>Ativo</span>
  <div class="ui-chkbox"><input value="Removido" type="checkbox" checked></div><span>Removido</span>
</div>
<script>
document.getElementById('trigger').addEventListener('click', function () {
  document.querySelector('.panel').style.display = 'block';
});
document.getElementById('all').addEventListener('click', function () {
  const next = this.checked;
  document.querySelectorAll('.panel input[type=checkbox]').forEach(cb => cb.checked = next);
});
document.querySelectorAll('.panel span').forEach(function (span) {
  span.addEventListener('click', function () {
    const input = span.previousElementSibling.querySelector('input');
    input.checked = !input.checked;
  });
});
</script>
"""


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    pg = browser.new_page()
    pg.set_default_timeout(1500)
    pg.set_content(MENU_HTML)
    yield pg
    pg.close()


def _ctx(params: dict, node_label: str = "Status") -> CodegenContext:
    return CodegenContext(node_id="test_node", params=params, in_loop=False, target_var="page", node_label=node_label)


def _exec_fragment(page, fragment: str, ns: dict | None = None) -> dict:
    if ns is None:
        ns = {}
        exec(compile(HEADER, "<header>", "exec"), ns)
    ns["page"] = page
    exec(compile(fragment, "<fragment>", "exec"), ns)
    return ns


def _base_params(**overrides) -> dict:
    params = {
        "triggerSelector": "#trigger",
        "triggerSelectorType": "css",
        "mode": "single",
        "optionText": "Aprovado",
    }
    params.update(overrides)
    return params


# --- catalog / registry ---------------------------------------------------


def test_node_registered_with_expected_shape():
    spec = NODE_REGISTRY["html_list_select"]
    assert spec.label == "Select List HTML"
    assert spec.category == "action"
    assert spec.icon == "list-select"
    assert spec.opens_block is False
    param_keys = {p.key for p in spec.params}
    assert {"triggerSelector", "clearSelector", "mode", "optionText", "optionTexts", "clearCheckedBeforeSelect", "matchType", "listContainerSelector", "bypassOnFailure"} <= param_keys


def test_get_node_catalog_includes_it():
    from app.services.workflow_reconstructor import build_node_catalog

    catalog = build_node_catalog()
    entry = next(c for c in catalog if c["type"] == "html_list_select")
    assert entry["category"] == "action"
    assert entry["icon"] == "list-select"


def test_validate_workflow_accepts_open_browser_html_list_select():
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(id="n2", type="html_list_select", position=Position(x=1, y=0), params=_base_params()),
    ]
    edges = [WFEdge(id="e1", source="n1", target="n2")]
    script = generate_script(nodes, edges, PROJECT_ID, workflow_id=WORKFLOW_ID)
    compile(script, "<generated>", "exec")


def test_missing_option_text_raises_codegen_error():
    with pytest.raises(CodegenError, match="Option Text"):
        codegen_html_list_select(_ctx(_base_params(optionText="")))


def test_empty_option_list_raises_codegen_error():
    with pytest.raises(CodegenError, match="at least one option"):
        codegen_html_list_select(_ctx(_base_params(mode="multiple", optionTexts=[])))


# --- real functional behavior ----------------------------------------------


def test_trigger_opens_the_menu(page):
    fragment = codegen_html_list_select(_ctx(_base_params()))
    _exec_fragment(page, fragment)
    assert page.is_visible(".panel")


def test_single_mode_clicks_the_right_option(page):
    fragment = codegen_html_list_select(_ctx(_base_params(optionText="Reprovado", resultVar="r")))
    ns = _exec_fragment(page, fragment)
    assert page.evaluate("window.__clickLog") == ["Reprovado"]
    assert ns["r"] == "Reprovado"


def test_multiple_mode_clicks_several_options_in_sequence(page):
    fragment = codegen_html_list_select(
        _ctx(_base_params(mode="multiple", optionTexts=["Aprovado", "Reprovado"], resultVar="r"))
    )
    ns = _exec_fragment(page, fragment)
    assert page.evaluate("window.__clickLog") == ["Aprovado", "Reprovado"]
    assert ns["r"] == {"clicked": ["Aprovado", "Reprovado"], "failed": []}


def test_multiple_mode_clears_native_and_aria_checked_options_first(browser):
    page = browser.new_page()
    page.set_default_timeout(1500)
    page.set_content(CHECKBOX_HTML)
    try:
        fragment = codegen_html_list_select(
            _ctx(
                _base_params(
                    mode="multiple",
                    optionTexts=["Removido"],
                    listContainerSelector=".panel",
                    listContainerSelectorType="css",
                )
            )
        )
        _exec_fragment(page, fragment)
        assert page.locator("input[value='Antigo']").is_checked() is False
        assert page.locator("input[value='Removido']").is_checked() is True
        assert page.locator("#aria-old").get_attribute("aria-checked") == "false"
    finally:
        page.close()


def test_multiple_mode_can_preserve_existing_checked_options(browser):
    page = browser.new_page()
    page.set_default_timeout(1500)
    page.set_content(CHECKBOX_HTML)
    try:
        fragment = codegen_html_list_select(
            _ctx(
                _base_params(
                    mode="multiple",
                    optionTexts=["Removido"],
                    clearCheckedBeforeSelect=False,
                    listContainerSelector=".panel",
                    listContainerSelectorType="css",
                )
            )
        )
        _exec_fragment(page, fragment)
        assert page.locator("input[value='Antigo']").is_checked() is True
        assert page.locator("input[value='Removido']").is_checked() is True
        assert page.locator("#aria-old").get_attribute("aria-checked") == "true"
    finally:
        page.close()


def test_multiple_mode_uses_master_visual_checkbox_to_clear_custom_container(browser):
    page = browser.new_page()
    page.set_default_timeout(1500)
    page.set_content(PRIMEFACES_CHECKBOX_HTML)
    try:
        fragment = codegen_html_list_select(
            _ctx(
                _base_params(
                    mode="multiple",
                    optionTexts=["Removido"],
                    listContainerSelector=".panel",
                    listContainerSelectorType="css",
                )
            )
        )
        _exec_fragment(page, fragment)
        assert page.locator("input[value='Ativo']").is_checked() is False
        assert page.locator("input[value='Removido']").is_checked() is True
    finally:
        page.close()


def test_clear_selector_is_clicked_before_selecting(page):
    fragment = codegen_html_list_select(_ctx(_base_params(clearSelector=".clear", clearSelectorType="css")))
    _exec_fragment(page, fragment)
    assert page.evaluate("window.__cleared") is True


def test_exact_match_does_not_match_a_superset_text(page):
    """"Pesquisar" (exact) must NOT match the "Pesquisar Avançado" <li> — proves exact
    matching actually disambiguates near-duplicate labels, the whole reason it's the
    default."""
    fragment = codegen_html_list_select(_ctx(_base_params(optionText="Pesquisar", matchType="exact")))
    _exec_fragment(page, fragment)
    assert page.evaluate("window.__clickLog") == ["Pesquisar"]


def test_contains_match_does_match_a_superset_text(page):
    """With matchType=contains, "Pesquisar" is ambiguous between the two <li> elements
    — Playwright's own strict-mode error is the expected (and desired) outcome."""
    fragment = codegen_html_list_select(_ctx(_base_params(optionText="Pesquisar", matchType="contains")))
    with pytest.raises(PlaywrightError, match="strict mode violation"):
        _exec_fragment(page, fragment)


def test_ambiguous_text_across_containers_raises_clear_error(browser):
    page = browser.new_page()
    page.set_default_timeout(1500)
    page.set_content(DUPLICATE_TEXT_HTML)
    try:
        fragment = codegen_html_list_select(_ctx(_base_params(optionText="Aprovado", matchType="exact")))
        with pytest.raises(PlaywrightError, match="strict mode violation"):
            _exec_fragment(page, fragment)
    finally:
        page.close()


def test_hidden_duplicate_is_ignored(browser):
    page = browser.new_page()
    page.set_default_timeout(1500)
    page.set_content(HIDDEN_DUPLICATE_TEXT_HTML)
    try:
        fragment = codegen_html_list_select(_ctx(_base_params(optionText="Removido", matchType="exact")))
        _exec_fragment(page, fragment)
        assert page.evaluate("window.__clickedOption") == "visible-option"
    finally:
        page.close()


def test_list_container_selector_disambiguates(browser):
    page = browser.new_page()
    page.set_default_timeout(1500)
    page.set_content(DUPLICATE_TEXT_HTML)
    try:
        fragment = codegen_html_list_select(
            _ctx(
                _base_params(
                    optionText="Aprovado",
                    matchType="exact",
                    listContainerSelector=".panel > ul:not(.other)",
                    listContainerSelectorType="css",
                )
            )
        )
        _exec_fragment(page, fragment)  # must NOT raise
    finally:
        page.close()


def test_bypass_on_failure_lets_other_options_through(page):
    fragment = codegen_html_list_select(
        _ctx(
            _base_params(
                mode="multiple",
                optionTexts=["Aprovado", "Does Not Exist", "Reprovado"],
                bypassOnFailure=True,
                resultVar="r",
            )
        )
    )
    ns = _exec_fragment(page, fragment)  # must NOT raise despite the missing option
    assert page.evaluate("window.__clickLog") == ["Aprovado", "Reprovado"]
    assert ns["r"]["clicked"] == ["Aprovado", "Reprovado"]
    assert ns["r"]["failed"] == ["Does Not Exist"]


def test_bypass_off_raises_on_missing_option(page):
    fragment = codegen_html_list_select(_ctx(_base_params(optionText="Does Not Exist")))
    with pytest.raises(PlaywrightError, match="Timeout"):
        _exec_fragment(page, fragment)
