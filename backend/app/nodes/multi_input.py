from app.codegen.context import CodegenContext, CodegenError
from app.codegen.template_utils import build_selector_literal, render_template_expr
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_multi_input(ctx: CodegenContext) -> str:
    rows = ctx.params.get("fields") or []
    if not isinstance(rows, list) or not rows:
        raise CodegenError(f"Node '{ctx.node_label}': add at least one field")

    lines: list[str] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise CodegenError(f"Node '{ctx.node_label}': field #{i + 1} is invalid")
        selector_raw = (row.get("selector") or "").strip()
        if not selector_raw:
            raise CodegenError(f"Node '{ctx.node_label}': field #{i + 1} is missing a selector")
        selector_type = row.get("selectorType") or "css"
        kind = row.get("kind") or "text"
        selector_expr = build_selector_literal(selector_raw, selector_type)
        value_expr = render_template_expr(row.get("value", ""), ctx)
        method = "select_option" if kind == "select" else "fill"
        lines.append(f"{ctx.target_var}.locator({selector_expr}).{method}({value_expr})")
    lines.append(f'print("[{ctx.node_id}] filled {len(rows)} field(s)")')
    return "\n".join(lines)


register(
    NodeSpec(
        type="multi_input",
        label="Multi Input",
        category="action",
        description=(
            "Fills or selects several fields in one step — add a row per field, each with its own "
            "selector, selector type (ID/Class/CSS/XPath/Full XPath), and whether it's a text input "
            "or a select dropdown. Runs top to bottom, in a single node."
        ),
        icon="rows",
        params=[
            ParamField(key="fields", label="Fields", type="fieldList", default=[]),
        ],
        codegen=codegen_multi_input,
    )
)
