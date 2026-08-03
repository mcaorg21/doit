from app.codegen.context import CodegenContext
from app.codegen.template_utils import render_template_expr
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_goto(ctx: CodegenContext) -> str:
    url_expr = render_template_expr(ctx.params.get("url", ""), ctx)
    return f'page.goto({url_expr})\nprint(f"[{ctx.node_id}] navigated to " + {url_expr})'


register(
    NodeSpec(
        type="goto",
        label="Navigate",
        category="action",
        description="Navigates the current page to a URL.",
        icon="navigation",
        params=[
            ParamField(
                key="url",
                label="URL",
                type="text",
                required=True,
                placeholder="https://example.com/signup",
                supportsTemplate=True,
            ),
        ],
        codegen=codegen_goto,
    )
)
