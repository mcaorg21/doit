from app.codegen.context import CodegenContext
from app.codegen.template_utils import render_template_expr, resolve_selector
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import fill_lines, selector_field, selector_type_field, typing_option_fields
from app.nodes.registry import register


def codegen_fill(ctx: CodegenContext) -> str:
    selector = resolve_selector(ctx)
    value_expr = render_template_expr(ctx.params.get("value", ""), ctx)
    locator_expr = f"{ctx.target_var}.locator({selector})"
    lines = fill_lines(locator_expr, value_expr, bool(ctx.params.get("clearFirst")), bool(ctx.params.get("simulateTyping")))
    lines.append(f'print(f"[{ctx.node_label}] filled " + {selector})')
    return "\n".join(lines)


register(
    NodeSpec(
        type="fill",
        label="Fill Input",
        category="action",
        description="Fills a text input identified by a selector.",
        example="Fills '#email' with 'john@example.com'",
        icon="rectangle-ellipsis",
        params=[
            selector_field(placeholder="email"),
            selector_type_field(),
            ParamField(key="value", label="Value", type="text", required=True, supportsTemplate=True),
            *typing_option_fields(),
        ],
        codegen=codegen_fill,
    )
)
