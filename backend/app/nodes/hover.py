from app.codegen.context import CodegenContext
from app.codegen.template_utils import resolve_selector
from app.nodes.base import NodeSpec
from app.nodes.common import selector_field, selector_type_field
from app.nodes.registry import register


def codegen_hover(ctx: CodegenContext) -> str:
    selector = resolve_selector(ctx)
    return f'page.hover({selector})\nprint(f"[{ctx.node_id}] hovered " + {selector})'


register(
    NodeSpec(
        type="hover",
        label="Hover",
        category="action",
        description="Hovers the mouse over an element identified by a selector.",
        icon="mouse-pointer-2",
        params=[
            selector_field(placeholder=".menu-item"),
            selector_type_field(),
        ],
        codegen=codegen_hover,
    )
)
