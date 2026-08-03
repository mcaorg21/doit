from app.codegen.context import CodegenContext
from app.codegen.template_utils import resolve_selector
from app.nodes.base import NodeSpec
from app.nodes.common import selector_field, selector_type_field
from app.nodes.registry import register


def codegen_click(ctx: CodegenContext) -> str:
    selector = resolve_selector(ctx)
    return f'page.click({selector})\nprint(f"[{ctx.node_id}] clicked " + {selector})'


register(
    NodeSpec(
        type="click",
        label="Click",
        category="action",
        description="Clicks an element identified by a selector.",
        icon="mouse-pointer-click",
        params=[
            selector_field(placeholder="button[type=submit]"),
            selector_type_field(),
        ],
        codegen=codegen_click,
    )
)
