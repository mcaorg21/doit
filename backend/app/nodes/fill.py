from app.codegen.context import CodegenContext
from app.codegen.template_utils import render_template_expr, resolve_selector
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import selector_field, selector_type_field
from app.nodes.registry import register


def codegen_fill(ctx: CodegenContext) -> str:
    selector = resolve_selector(ctx)
    value_expr = render_template_expr(ctx.params.get("value", ""), ctx)
    return f'page.fill({selector}, {value_expr})\nprint(f"[{ctx.node_id}] filled " + {selector})'


register(
    NodeSpec(
        type="fill",
        label="Fill Input",
        category="action",
        description="Fills a text input identified by a selector.",
        icon="rectangle-ellipsis",
        params=[
            selector_field(placeholder="email"),
            selector_type_field(),
            ParamField(key="value", label="Value", type="text", required=True, supportsTemplate=True),
        ],
        codegen=codegen_fill,
    )
)
