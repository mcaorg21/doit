from app.codegen.context import CodegenContext
from app.codegen.template_utils import resolve_selector, validate_identifier
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import selector_field, selector_type_field, timeout_field, timeout_ms_kwarg
from app.nodes.registry import register


def codegen_get_text(ctx: CodegenContext) -> str:
    selector = resolve_selector(ctx)
    var = validate_identifier(ctx.params.get("resultVar", ""), ctx, "Result Variable")
    timeout_kwarg = timeout_ms_kwarg(ctx.params)
    locator_expr = f"{ctx.target_var}.locator({selector})"
    return (
        # Explicit wait_for before reading — an unstable/slow site can take a while to
        # actually render the element, and .inner_text() alone only waits for the
        # DEFAULT Playwright timeout (30s, not configurable per-call the same way).
        # Waiting here first means the Timeout param below actually controls how long
        # this node is willing to wait, instead of silently falling back to 30s.
        f"{locator_expr}.wait_for(state='visible', {timeout_kwarg})\n"
        f"{var} = {locator_expr}.inner_text()\n"
        f'print(f"[{ctx.node_label}] {var} = " + {var})'
    )


register(
    NodeSpec(
        type="get_text",
        label="Get Text",
        category="action",
        description=(
            "Waits for an element matching a selector (ID/Class/CSS/XPath/Full XPath) to appear, then "
            "reads its visible text and stores it in a variable, ready to reference elsewhere as "
            "{{varName}} or feed a Loop node. The explicit wait (with a configurable Timeout) protects "
            "against a slow/unstable site where the element hasn't rendered yet."
        ),
        example="Waits for '#price' to appear, then reads its text into the variable 'price'",
        icon="scan-text",
        params=[
            selector_field(placeholder="price"),
            selector_type_field(),
            timeout_field(),
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
