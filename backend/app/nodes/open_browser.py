from app.codegen.context import CodegenContext
from app.codegen.template_utils import validate_safe_name
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def _profile_name(ctx: CodegenContext) -> str:
    return (ctx.params.get("profileName") or "").strip()


def codegen_open_browser(ctx: CodegenContext) -> str:
    params = ctx.params
    headless = bool(params.get("headless", False))
    channel = params.get("browserChannel", "chrome")
    profile = _profile_name(ctx)

    if profile:
        safe_profile = validate_safe_name(profile, ctx, "Profile Name")
        profile_dir = repr(f"profiles/{safe_profile}")
        lines = [
            "with sync_playwright() as p:",
            f"    context = p.chromium.launch_persistent_context({profile_dir}, channel={channel!r}, headless={headless})",
            "    page = context.pages[0] if context.pages else context.new_page()",
            f'    print("[{ctx.node_id}] browser launched (profile: {safe_profile})")',
        ]
    else:
        lines = [
            "with sync_playwright() as p:",
            f"    browser = p.chromium.launch(channel={channel!r}, headless={headless})",
            "    page = browser.new_page()",
            f'    print("[{ctx.node_id}] browser launched")',
        ]
    return "\n".join(lines)


def closing_stmt_open_browser(ctx: CodegenContext) -> str:
    return "context.close()" if _profile_name(ctx) else "browser.close()"


def browser_var_after_open_browser(ctx: CodegenContext) -> str:
    return "context" if _profile_name(ctx) else "browser"


register(
    NodeSpec(
        type="open_browser",
        label="Open Browser",
        category="browser",
        description="Launches Chrome via Playwright and creates a new page.",
        icon="chrome",
        opens_block=True,
        closing_stmt=closing_stmt_open_browser,
        browser_var_after=browser_var_after_open_browser,
        params=[
            ParamField(key="headless", label="Headless", type="boolean", default=False),
            ParamField(
                key="browserChannel",
                label="Browser",
                type="select",
                default="chrome",
                options=[{"value": "chrome", "label": "Chrome"}, {"value": "chromium", "label": "Chromium"}],
            ),
            ParamField(
                key="profileName",
                label="Profile Name (optional)",
                type="text",
                placeholder="my-profile",
            ),
        ],
        codegen=codegen_open_browser,
    )
)
