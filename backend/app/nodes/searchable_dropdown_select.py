from app.codegen.context import CodegenContext, CodegenError
from app.codegen.template_utils import render_template_expr, resolve_selector, validate_identifier
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import SELECTOR_TYPE_OPTIONS, fill_lines, typing_option_fields
from app.nodes.registry import register


def codegen_searchable_dropdown_select(ctx: CodegenContext) -> str:
    params = ctx.params
    trigger = resolve_selector(ctx, "triggerSelector", "triggerSelectorType")
    search_input = resolve_selector(ctx, "inputSelector", "inputSelectorType")
    search_text_raw = params.get("searchText") or ""
    if not isinstance(search_text_raw, str) or not search_text_raw.strip():
        raise CodegenError(f"Node '{ctx.node_label}': 'Search Text' is required")

    search_text = render_template_expr(search_text_raw, ctx)
    timeout_ms = int(float(params.get("timeout") or 30) * 1000)
    result_var_raw = (params.get("resultVar") or "").strip()
    result_var = validate_identifier(result_var_raw, ctx, "Result Variable") if result_var_raw else None

    lines = [
        f"_searchable_trigger = {ctx.target_var}.locator({trigger})",
        f"_searchable_trigger.click(timeout={timeout_ms})",
        f"_searchable_input = {ctx.target_var}.locator({search_input}).filter(visible=True)",
        f"_searchable_input.wait_for(state='visible', timeout={timeout_ms})",
        *fill_lines("_searchable_input", search_text, bool(params.get("clearFirst")), bool(params.get("simulateTyping"))),
        "_searchable_input.press('Enter')",
        f'print(f"[{ctx.node_label}] searched and confirmed " + {search_text})',
    ]
    if result_var:
        lines.append(f"{result_var} = {search_text}")
    return "\n".join(lines)


register(
    NodeSpec(
        type="searchable_dropdown_select",
        label="Select Searchable Dropdown",
        category="action",
        description=(
            "Selects an item in a searchable custom dropdown: clicks the field, waits for the visible "
            "search input, fills the desired text, and confirms it with Enter. The trigger and input "
            "selectors are independent so the node works with different component libraries."
        ),
        example="Opens a report-model dropdown, types 'DADOS DO PROCESSO', and presses Enter",
        icon="list-select",
        params=[
            ParamField(key="triggerSelector", label="Trigger Selector (opens the dropdown)", type="text", required=True, placeholder="#model-dropdown"),
            ParamField(key="triggerSelectorType", label="Trigger Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(key="inputSelector", label="Search Input Selector", type="text", required=True, placeholder=".dropdown-panel input"),
            ParamField(key="inputSelectorType", label="Search Input Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(key="searchText", label="Search Text", type="text", required=True, supportsTemplate=True, placeholder="DADOS DO PROCESSO"),
            *typing_option_fields(),
            ParamField(key="timeout", label="Timeout (seconds)", type="number", default=30),
            ParamField(key="resultVar", label="Result Variable (optional)", type="text", placeholder="selected", producesVariable=True),
        ],
        codegen=codegen_searchable_dropdown_select,
    )
)
