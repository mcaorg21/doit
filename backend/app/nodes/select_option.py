from app.codegen.context import CodegenContext
from app.codegen.template_utils import render_template_expr, resolve_selector
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import selector_field, selector_type_field
from app.nodes.registry import register


def codegen_select_option(ctx: CodegenContext) -> str:
    selector = resolve_selector(ctx)
    value_expr = render_template_expr(ctx.params.get("value", ""), ctx)
    return (
        f"{ctx.target_var}.locator({selector}).select_option({value_expr})\n"
        f'print(f"[{ctx.node_label}] selected option on " + {selector})'
    )


register(
    NodeSpec(
        type="select_option",
        label="Select Option",
        category="action",
        description="Selects an option in a <select> element identified by a selector.",
        icon="chevrons-up-down",
        params=[
            selector_field(placeholder="country"),
            selector_type_field(),
            ParamField(key="value", label="Option Value", type="text", required=True, supportsTemplate=True),
        ],
        codegen=codegen_select_option,
    )
)
