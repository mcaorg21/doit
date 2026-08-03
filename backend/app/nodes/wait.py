from app.codegen.context import CodegenContext
from app.codegen.template_utils import resolve_selector
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import selector_type_field
from app.nodes.registry import register


def codegen_wait(ctx: CodegenContext) -> str:
    if ctx.params.get("waitType") == "element":
        selector = resolve_selector(ctx)
        return f'page.wait_for_selector({selector})\nprint(f"[{ctx.node_id}] waited for element " + {selector})'

    try:
        seconds = float(ctx.params.get("duration") or 1)
    except (TypeError, ValueError):
        seconds = 1.0
    ms = int(seconds * 1000)
    return f'page.wait_for_timeout({ms})\nprint("[{ctx.node_id}] waited {seconds}s")'


register(
    NodeSpec(
        type="wait",
        label="Wait",
        category="action",
        description="Pauses execution either for a fixed duration or until an element appears on the page.",
        icon="clock",
        params=[
            ParamField(
                key="waitType",
                label="Wait For",
                type="select",
                default="time",
                options=[
                    {"value": "time", "label": "Time (seconds)"},
                    {"value": "element", "label": "Element to appear"},
                ],
            ),
            ParamField(key="duration", label="Duration (seconds)", type="number", default=1),
            ParamField(
                key="selector",
                label="Selector Value (when waiting for an element)",
                type="text",
                placeholder="loaded",
            ),
            selector_type_field(),
        ],
        codegen=codegen_wait,
    )
)
