from app.codegen.context import CodegenContext
from app.codegen.template_utils import resolve_selector, validate_identifier
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import selector_field, selector_type_field
from app.nodes.registry import register


def codegen_get_text(ctx: CodegenContext) -> str:
    selector = resolve_selector(ctx)
    var = validate_identifier(ctx.params.get("resultVar", ""), ctx, "Result Variable")
    return f'{var} = {ctx.target_var}.locator({selector}).inner_text()\nprint(f"[{ctx.node_label}] {var} = " + {var})'


register(
    NodeSpec(
        type="get_text",
        label="Get Text",
        category="action",
        description=(
            "Reads the visible text of an element matching a selector (ID/Class/CSS/XPath/Full XPath) "
            "and stores it in a variable, ready to reference elsewhere as {{varName}} or feed a Loop node."
        ),
        icon="scan-text",
        params=[
            selector_field(placeholder="price"),
            selector_type_field(),
            ParamField(
                key="resultVar",
                label="Result Variable",
                type="text",
                required=True,
                placeholder="price_text",
                producesVariable=True,
            ),
        ],
        codegen=codegen_get_text,
    )
)
