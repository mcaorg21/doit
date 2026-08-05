from app.codegen.context import CodegenContext
from app.codegen.template_utils import resolve_selector
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import selector_type_field
from app.nodes.registry import register


def _raw_selector(ctx: CodegenContext) -> str:
    return (ctx.params.get("selector") or "").strip()


def codegen_switch_frame(ctx: CodegenContext) -> str:
    if not _raw_selector(ctx):
        return f'print("[{ctx.node_label}] switched to default content (main page)")'
    selector = resolve_selector(ctx)
    return f'frame = page.frame_locator({selector})\nprint(f"[{ctx.node_label}] switched to iframe " + {selector})'


def target_var_after_switch_frame(ctx: CodegenContext) -> str:
    return "page" if not _raw_selector(ctx) else "frame"


register(
    NodeSpec(
        type="switch_frame",
        label="Switch Frame",
        category="browser",
        description=(
            "Switches into an iframe by selector for the actions that follow (Fill, Click, "
            "Hover, Select Option, Wait, Element Present?). Always resolves fresh from the "
            "main page first, so it never ends up nested inside a previous frame — "
            "equivalent to Selenium's switch_to.default_content() followed by "
            "switch_to.frame(id). Leave the selector empty to switch back to the main page."
        ),
        icon="frame",
        params=[
            ParamField(
                key="selector",
                label="Selector Value (blank = switch back to main page)",
                type="text",
                required=False,
                placeholder="my-iframe",
            ),
            selector_type_field(),
        ],
        codegen=codegen_switch_frame,
        target_var_after=target_var_after_switch_frame,
    )
)
