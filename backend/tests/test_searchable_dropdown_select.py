import pytest
from playwright.sync_api import sync_playwright

from app.codegen.context import CodegenContext, CodegenError
from app.codegen.engine import HEADER, generate_script
from app.models.workflow import Position, WFEdge, WFNode
from app.nodes.registry import NODE_REGISTRY
from app.nodes.searchable_dropdown_select import codegen_searchable_dropdown_select


def _ctx(params):
    return CodegenContext(node_id="n", params=params, in_loop=False, target_var="page", node_label="Modelo")


def _params(**overrides):
    value = {
        "triggerSelector": "#trigger",
        "triggerSelectorType": "css",
        "inputSelector": ".panel input",
        "inputSelectorType": "css",
        "searchText": "DADOS DO PROCESSO",
    }
    value.update(overrides)
    return value


def test_registered_and_generates_valid_workflow():
    spec = NODE_REGISTRY["searchable_dropdown_select"]
    assert spec.label == "Select Searchable Dropdown"
    assert {"triggerSelector", "inputSelector", "searchText", "timeout", "resultVar"} <= {p.key for p in spec.params}
    nodes = [
        WFNode(id="n1", type="open_browser", position=Position(x=0, y=0), params={"headless": True}),
        WFNode(id="n2", type=spec.type, position=Position(x=1, y=0), params=_params()),
    ]
    compile(generate_script(nodes, [WFEdge(id="e", source="n1", target="n2")], "p", workflow_id="w"), "<generated>", "exec")


def test_requires_search_text():
    with pytest.raises(CodegenError, match="Search Text"):
        codegen_searchable_dropdown_select(_ctx(_params(searchText="")))


def test_registered_with_typing_option_params():
    spec = NODE_REGISTRY["searchable_dropdown_select"]
    assert {"clearFirst", "simulateTyping"} <= {p.key for p in spec.params}


def test_clear_first_and_simulate_typing_still_selects_and_confirms():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content("""
          <button id='trigger'>Modelo</button>
          <div class='panel' style='display:none'><input value='old'></div>
          <script>
            window.__inputEvents = 0;
            trigger.onclick = () => document.querySelector('.panel').style.display = 'block';
            document.querySelector('input').addEventListener('input', () => { window.__inputEvents++; });
            document.querySelector('input').onkeydown = e => {
              if (e.key === 'Enter') window.__selected = e.target.value;
            };
          </script>
        """)
        ns = {}
        exec(compile(HEADER, "<header>", "exec"), ns)
        ns["page"] = page
        fragment = codegen_searchable_dropdown_select(
            _ctx(_params(resultVar="selected", clearFirst=True, simulateTyping=True))
        )
        assert ".clear()" in fragment
        assert ".press_sequentially(" in fragment
        assert ".fill(" not in fragment
        exec(compile(fragment, "<fragment>", "exec"), ns)
        assert page.evaluate("window.__selected") == "DADOS DO PROCESSO"
        assert ns["selected"] == "DADOS DO PROCESSO"
        # +1 for .clear()'s own input event (clearing the pre-filled "old"), then one
        # more per typed character from press_sequentially.
        assert page.evaluate("window.__inputEvents") == len("DADOS DO PROCESSO") + 1
        browser.close()


def test_clicks_fills_and_confirms_with_enter():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content("""
          <button id='trigger'>Modelo</button>
          <div class='panel' style='display:none'><input></div>
          <script>
            trigger.onclick = () => document.querySelector('.panel').style.display = 'block';
            document.querySelector('input').onkeydown = e => {
              if (e.key === 'Enter') window.__selected = e.target.value;
            };
          </script>
        """)
        ns = {}
        exec(compile(HEADER, "<header>", "exec"), ns)
        ns["page"] = page
        exec(compile(codegen_searchable_dropdown_select(_ctx(_params(resultVar="selected"))), "<fragment>", "exec"), ns)
        assert page.evaluate("window.__selected") == "DADOS DO PROCESSO"
        assert ns["selected"] == "DADOS DO PROCESSO"
        browser.close()
