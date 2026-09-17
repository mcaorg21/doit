import uuid

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
    # Auto-open Chrome DevTools — only true for a live/voice-guided build session
    # (app/mcp/live_sessions.py sets has_breakpoints explicitly); a real run
    # ("Run workflow", a schedule/webhook trigger, ...) never does, even if the
    # workflow has a Pause node or a breakpoint on a connector — DevTools popping up
    # uninvited there wasn't wanted. Playwright's launch()/launch_persistent_context()
    # have no `devtools` kwarg (that's a Puppeteer-ism) — the actual mechanism is the
    # underlying Chromium flag, passed through `args`.
    devtools = ctx.has_breakpoints and channel == "chrome" and not headless
    args_expr = "['--auto-open-devtools-for-tabs']" if devtools else "[]"

    if profile:
        safe_profile = validate_safe_name(profile, ctx, "Profile Name")
        multi_user = bool(params.get("multiUser", False))
        if multi_user:
            # A persistent profile dir is exclusively locked by Chromium while in use —
            # fine for a single-user automation reusing one login, but two concurrent
            # runs against the *same* dir (e.g. a Webhook trigger called by several
            # people at once) would collide. Baking a random suffix in at codegen time
            # is safe because generate_script() runs fresh for every individual
            # execution (see runner.start_run/scheduler.py/webhook_registry.py), so
            # each run gets its own never-reused profile directory instead.
            run_suffix = uuid.uuid4().hex[:8]
            profile_dir = repr(f"profiles/{safe_profile}-{run_suffix}")
        else:
            profile_dir = repr(f"profiles/{safe_profile}")
        lines = [
            "with sync_playwright() as p:",
            f"    context = p.chromium.launch_persistent_context({profile_dir}, channel={channel!r}, headless={headless}, args={args_expr})",
            "    page = context.pages[0] if context.pages else context.new_page()",
            f'    print("[{ctx.node_label}] browser launched (profile: {safe_profile})")',
        ]
    else:
        lines = [
            "with sync_playwright() as p:",
            f"    browser = p.chromium.launch(channel={channel!r}, headless={headless}, args={args_expr})",
            "    page = browser.new_page()",
            f'    print("[{ctx.node_label}] browser launched")',
        ]
    return "\n".join(lines)


def closing_stmt_open_browser(ctx: CodegenContext) -> str:
    return "context.close()" if _profile_name(ctx) else "browser.close()"


def browser_var_after_open_browser(ctx: CodegenContext) -> str:
    return "context" if _profile_name(ctx) else "browser"


def target_var_after_open_browser(ctx: CodegenContext) -> str:
    return "page"


register(
    NodeSpec(
        type="open_browser",
        label="Open Browser",
        category="browser",
        description="Launches Chrome via Playwright and creates a new page.",
        example='Launches Chrome (visible) and opens a blank page',
        icon="chrome",
        opens_block=True,
        closing_stmt=closing_stmt_open_browser,
        browser_var_after=browser_var_after_open_browser,
        target_var_after=target_var_after_open_browser,
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
            ParamField(
                key="multiUser",
                label="Multi-user (isolate profile per run — for workflows multiple people can trigger at once)",
                type="boolean",
                default=False,
            ),
        ],
        codegen=codegen_open_browser,
    )
)
