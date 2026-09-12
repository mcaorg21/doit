from app.codegen.context import CodegenContext, CodegenError
from app.codegen.template_utils import render_template_expr, resolve_credential_pair
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_browser_2captcha(ctx: CodegenContext) -> str:
    user_expr, password_expr = resolve_credential_pair(ctx, "credentialId", "2Captcha Browser Login")

    profile_id_raw = (ctx.params.get("profileId") or "").strip()
    if not profile_id_raw:
        raise CodegenError(f"Node '{ctx.node_label}': 'Profile ID' is required")
    profile_id_expr = render_template_expr(profile_id_raw, ctx)

    country_code = (ctx.params.get("countryCode") or "en").strip() or "en"
    country_code_expr = repr(country_code)

    # country_code/profile_id are only ever spliced in as *runtime variables*
    # referenced inside the f-string below, never as raw text inside the f-string's
    # own source — a user-typed value with a stray quote in it must never be able to
    # break out of the generated Python source itself.
    lines = [
        "with sync_playwright() as p:",
        f"    _cb_user = {user_expr}",
        f"    _cb_password = {password_expr}",
        f"    _cb_profile = {profile_id_expr}",
        f"    _cb_country = {country_code_expr}",
        "    _cb_cdp_url = f'ws://{_cb_user}-pid-{_cb_profile}-zone-scraping_browser-country-{_cb_country}:{_cb_password}@cb.2captcha.com:9222'",
        "    browser = p.chromium.connect_over_cdp(_cb_cdp_url)",
        "    context = browser.contexts[0]",
        "    page = context.new_page()",
        f'    print("[{ctx.node_label}] connected to 2Captcha cloud browser (profile: " + str(_cb_profile) + ")")',
    ]
    return "\n".join(lines)


def closing_stmt_browser_2captcha(ctx: CodegenContext) -> str:
    return "browser.close()"


def browser_var_after_browser_2captcha(ctx: CodegenContext) -> str:
    return "browser"


def target_var_after_browser_2captcha(ctx: CodegenContext) -> str:
    return "page"


register(
    NodeSpec(
        type="browser_2captcha",
        label="Browser (2Captcha)",
        category="browser",
        description=(
            "Connects to a cloud browser via 2Captcha's Scraping Browser instead of "
            "launching a local one — useful when you want the browsing/IP to happen "
            "off-machine. Requires a '2captcha_browser' credential whose Value is "
            "'login:password' (from your 2Captcha Scraping Browser dashboard) plus a "
            "Profile ID."
        ),
        example='Connects to a 2Captcha Scraping Browser instead of a local Chrome',
        icon="cloud",
        opens_block=True,
        closing_stmt=closing_stmt_browser_2captcha,
        browser_var_after=browser_var_after_browser_2captcha,
        target_var_after=target_var_after_browser_2captcha,
        params=[
            ParamField(
                key="credentialId",
                label="2Captcha Browser Login",
                type="text",
                required=True,
                credentialType="2captcha_browser",
            ),
            ParamField(
                key="profileId",
                label="Profile ID",
                type="text",
                required=True,
                supportsTemplate=True,
                placeholder="p01d566a6f1ab19321d097cf621d9748",
            ),
            ParamField(key="countryCode", label="Country Code", type="text", default="en"),
        ],
        codegen=codegen_browser_2captcha,
    )
)
