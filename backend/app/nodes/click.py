from app.codegen.context import CodegenContext
from app.codegen.template_utils import resolve_selector
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import selector_field, selector_type_field
from app.nodes.registry import register


def codegen_click(ctx: CodegenContext) -> str:
    selector = resolve_selector(ctx)
    click_stmt = f"{ctx.target_var}.locator({selector}).click()"
    success_print = f'print(f"[{ctx.node_label}] clicked " + {selector})'
    if not bool(ctx.params.get("bypassOnFailure")):
        return f"{click_stmt}\n{success_print}"
    # Bypass on: this node's own try/except swallows a failed click instead of
    # letting it reach the engine's auto-wrap breakpoint() — for elements that may or
    # may not be there (an optional banner, a cookie prompt that doesn't always show
    # up) where stopping the whole run to ask a human isn't worth it.
    fail_print = f'print(f"[{ctx.node_label}] click failed, continuing (bypass on) \u2014 " + str(_e))'
    return "try:\n" f"    {click_stmt}\n" f"    {success_print}\n" "except Exception as _e:\n" f"    {fail_print}"


register(
    NodeSpec(
        type="click",
        label="Click",
        category="action",
        description="Clicks an element identified by a selector.",
        example="Clicks the button matching '#submit'",
        icon="mouse-pointer-click",
        params=[
            selector_field(placeholder="button[type=submit]"),
            selector_type_field(),
            ParamField(
                key="bypassOnFailure",
                label="Bypass — continue the run even if this click fails",
                type="boolean",
                default=False,
            ),
        ],
        codegen=codegen_click,
    )
)
