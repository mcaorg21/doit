from app.codegen.context import CodegenContext, CodegenError
from app.codegen.template_utils import build_selector_literal
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_multi_click(ctx: CodegenContext) -> str:
    rows = ctx.params.get("clicks") or []
    if not isinstance(rows, list) or not rows:
        raise CodegenError(f"Node '{ctx.node_label}': add at least one click")

    lines: list[str] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise CodegenError(f"Node '{ctx.node_label}': click #{i + 1} is invalid")
        selector_raw = (row.get("selector") or "").strip()
        if not selector_raw:
            raise CodegenError(f"Node '{ctx.node_label}': click #{i + 1} is missing a selector")
        selector_type = row.get("selectorType") or "css"
        selector_expr = build_selector_literal(selector_raw, selector_type)
        lines.append(f"{ctx.target_var}.locator({selector_expr}).click()")
    lines.append(f'print("[{ctx.node_label}] clicked {len(rows)} element(s)")')
    return "\n".join(lines)


register(
    NodeSpec(
        type="multi_click",
        label="Multi Click",
        category="action",
        description=(
            "Clicks several elements in one step — add a row per element, each with its own "
            "selector and selector type (ID/Class/CSS/XPath/Full XPath). Runs top to bottom, "
            "in a single node, one click after another."
        ),
        example="Clicks '.tab-1' then '.tab-2' in sequence",
        icon="list-checks",
        params=[
            ParamField(key="clicks", label="Clicks", type="clickList", default=[]),
        ],
        codegen=codegen_multi_click,
    )
)
