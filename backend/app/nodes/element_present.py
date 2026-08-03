from app.codegen.context import CodegenContext
from app.codegen.template_utils import resolve_selector, validate_identifier
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import selector_field, selector_type_field
from app.nodes.registry import register


def codegen_element_present(ctx: CodegenContext) -> str:
    selector = resolve_selector(ctx)
    var = validate_identifier(ctx.params.get("resultVar", ""), ctx, "Result Variable")
    return f'{var} = page.locator({selector}).count() > 0\nprint(f"[{ctx.node_id}] {var} = " + str({var}))'


register(
    NodeSpec(
        type="element_present",
        label="Element Present?",
        category="logic",
        description=(
            "Checks whether an element matching a selector currently exists on the page "
            "(e.g. to detect whether login succeeded), storing True/False in a variable for a "
            "later IF node to branch on."
        ),
        icon="scan-search",
        params=[
            selector_field(placeholder="logged-in-badge"),
            selector_type_field(),
            ParamField(key="resultVar", label="Result Variable", type="text", required=True, placeholder="logged_in"),
        ],
        codegen=codegen_element_present,
    )
)
