from app.codegen.context import CodegenContext, CodegenError
from app.nodes.base import NodeSpec
from app.nodes.registry import register


def codegen_close_browser(ctx: CodegenContext) -> str:
    if ctx.browser_var is None:
        raise CodegenError(
            f"Node '{ctx.node_label}' (Close Browser) has no browser open before it — add an Open Browser node earlier in the chain"
        )
    var = ctx.browser_var
    return f'{var}.close()\nprint("[{ctx.node_id}] browser closed")'


def browser_var_after_close_browser(ctx: CodegenContext) -> None:
    return None


register(
    NodeSpec(
        type="close_browser",
        label="Close Browser",
        category="browser",
        description=(
            "Closes the browser opened by Open Browser (equivalent to Selenium's quit()). "
            "Optional — the browser is already closed automatically at the end of its "
            "block even without this node; use this to close it early, mid-flow."
        ),
        icon="circle-x",
        params=[],
        codegen=codegen_close_browser,
        browser_var_after=browser_var_after_close_browser,
    )
)
