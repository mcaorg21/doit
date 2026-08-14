from dataclasses import replace

from app.codegen.context import CodegenContext
from app.codegen.template_utils import resolve_selector
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import selector_type_field
from app.nodes.registry import register


def codegen_wait(ctx: CodegenContext) -> str:
    if ctx.params.get("waitType") == "element":
        selector = resolve_selector(ctx)
        try:
            timeout_s = float(ctx.params.get("timeout") or 10)
        except (TypeError, ValueError):
            timeout_s = 10.0
        timeout_ms = int(timeout_s * 1000)
        # Caught here (not left to the node's own outer try/except, which would drop
        # into pdb) so a timed-out wait just moves on to the next node instead of
        # stopping the run — that's the whole point of giving it a timeout at all.
        return (
            "try:\n"
            f"    {ctx.target_var}.locator({selector}).wait_for(timeout={timeout_ms})\n"
            f'    print(f"[{ctx.node_label}] element appeared: " + {selector})\n'
            "except Exception:\n"
            f'    print(f"[{ctx.node_label}] timed out after {timeout_s}s waiting for element, continuing: " + {selector})'
        )

    try:
        seconds = float(ctx.params.get("duration") or 1)
    except (TypeError, ValueError):
        seconds = 1.0
    ms = int(seconds * 1000)
    return f'page.wait_for_timeout({ms})\nprint("[{ctx.node_label}] waited {seconds}s")'


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
            ParamField(
                key="duration",
                label="Duration (seconds)",
                type="number",
                default=1,
                visibleWhen={"key": "waitType", "equals": "time"},
            ),
            ParamField(
                key="selector",
                label="Selector Value",
                type="text",
                placeholder="loaded",
                visibleWhen={"key": "waitType", "equals": "element"},
            ),
            replace(selector_type_field(), visibleWhen={"key": "waitType", "equals": "element"}),
            ParamField(
                key="timeout",
                label="Timeout (seconds)",
                type="number",
                default=10,
                visibleWhen={"key": "waitType", "equals": "element"},
            ),
        ],
        codegen=codegen_wait,
    )
)
