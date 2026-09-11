from app.codegen.context import CodegenContext, CodegenError
from app.codegen.template_utils import (
    render_template_expr,
    resolve_credential_pair,
    resolve_selector,
    validate_identifier,
)
from app.config import cookies_dir
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import SELECTOR_TYPE_OPTIONS
from app.nodes.registry import register


def codegen_microsoft_login(ctx: CodegenContext) -> str:
    """Generate a credential-backed, two-page Microsoft sign-in flow."""
    params = ctx.params
    url_raw = (params.get("url") or "").strip()
    if not url_raw:
        raise CodegenError(f"Node '{ctx.node_label}': 'URL' is required")

    url_expr = render_template_expr(url_raw, ctx)
    login_expr, password_expr = resolve_credential_pair(ctx, "credentialId", "Microsoft Login Credential")
    username_selector = resolve_selector(ctx, "usernameSelector", "usernameSelectorType")
    username_submit_selector = resolve_selector(ctx, "usernameSubmitSelector", "usernameSubmitSelectorType")
    password_selector = resolve_selector(ctx, "passwordSelector", "passwordSelectorType")
    password_submit_selector = resolve_selector(ctx, "passwordSubmitSelector", "passwordSubmitSelectorType")
    confirm_selector = resolve_selector(ctx, "confirmSelector", "confirmSelectorType")

    try:
        step_timeout_ms = float(params.get("stepTimeout") or 30) * 1000
    except (TypeError, ValueError):
        step_timeout_ms = 30000
    try:
        confirm_timeout_ms = float(params.get("confirmTimeout") or 60) * 1000
    except (TypeError, ValueError):
        confirm_timeout_ms = 60000

    cookies_dir_literal = repr(str(cookies_dir(ctx.project_id, ctx.workflow_id)))
    filename_raw = (params.get("cookiesFilename") or "microsoft-cookies.json").strip() or "microsoft-cookies.json"
    filename_expr = render_template_expr(filename_raw, ctx)
    stay_signed_in_raw = (params.get("staySignedInSelector") or "").strip()
    stay_signed_in_selector = (
        resolve_selector(ctx, "staySignedInSelector", "staySignedInSelectorType")
        if stay_signed_in_raw
        else None
    )
    result_var_raw = (params.get("resultVar") or "").strip()
    result_var = validate_identifier(result_var_raw, ctx, "Result Variable") if result_var_raw else None

    lines = [
        f"_ms_ck_dir = {cookies_dir_literal}",
        f"_ms_ck_path = os.path.join(_ms_ck_dir, {filename_expr})",
        "if os.path.exists(_ms_ck_path):",
        "    _ms_ck_data = json.loads(open(_ms_ck_path, encoding='utf-8').read())",
        "    page.context.add_cookies(_ms_ck_data)",
        f'    print(f"[{ctx.node_label}] loaded {{len(_ms_ck_data)}} cookie(s)")',
        f"page.goto({url_expr})",
        "_ms_already_ok = False",
        "try:",
        f"    page.locator({confirm_selector}).wait_for(timeout={step_timeout_ms:g})",
        "    _ms_already_ok = True",
        f'    print("[{ctx.node_label}] existing Microsoft session is valid")',
        "except Exception:",
        "    pass",
        "if not _ms_already_ok:",
        f"    page.locator({username_selector}).wait_for(timeout={step_timeout_ms:g})",
        f"    page.locator({username_selector}).fill({login_expr})",
        f"    page.locator({username_submit_selector}).click()",
        f"    page.locator({password_selector}).wait_for(timeout={step_timeout_ms:g})",
        f"    page.locator({password_selector}).fill({password_expr})",
        f"    page.locator({password_submit_selector}).click()",
    ]
    if stay_signed_in_selector:
        lines += [
            "    try:",
            f"        page.locator({stay_signed_in_selector}).click(timeout={step_timeout_ms:g})",
            "    except Exception:",
            "        pass",
        ]
    lines += [
        f"    page.locator({confirm_selector}).wait_for(timeout={confirm_timeout_ms:g})",
        "    _ms_ck_data = page.context.cookies()",
        "    os.makedirs(_ms_ck_dir, exist_ok=True)",
        "    open(_ms_ck_path, 'w', encoding='utf-8').write(json.dumps(_ms_ck_data))",
        f'    print(f"[{ctx.node_label}] login confirmed; saved {{len(_ms_ck_data)}} cookie(s)")',
    ]
    if result_var:
        lines.append(f"{result_var} = {{'alreadyLoggedIn': _ms_already_ok}}")
    return "\n".join(lines)


register(
    NodeSpec(
        type="microsoft_login",
        label="Microsoft Login",
        category="browser",
        description=(
            "Signs in through Microsoft's two-step username/password pages using a project login credential, "
            "then saves cookies for later runs. Use a confirmation selector that only exists inside the target app."
        ),
        icon="log-in",
        params=[
            ParamField(key="url", label="Application URL", type="text", required=True, supportsTemplate=True),
            ParamField(
                key="credentialId",
                label="Microsoft Login Credential",
                type="text",
                required=True,
                credentialType="login",
            ),
            ParamField(key="usernameSelector", label="Username Field Selector", type="text", required=True, default="input[type='email']"),
            ParamField(key="usernameSelectorType", label="Username Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(key="usernameSubmitSelector", label="Username Next Button Selector", type="text", required=True, default="input[type='submit']"),
            ParamField(key="usernameSubmitSelectorType", label="Username Next Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(key="passwordSelector", label="Password Field Selector", type="text", required=True, default="input[type='password']"),
            ParamField(key="passwordSelectorType", label="Password Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(key="passwordSubmitSelector", label="Password Sign-in Button Selector", type="text", required=True, default="input[type='submit']"),
            ParamField(key="passwordSubmitSelectorType", label="Password Sign-in Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(key="staySignedInSelector", label="Stay Signed In Button Selector (optional)", type="text", default="#idBtn_Back"),
            ParamField(key="staySignedInSelectorType", label="Stay Signed In Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(key="confirmSelector", label="Logged-in Confirmation Selector", type="text", required=True),
            ParamField(key="confirmSelectorType", label="Confirmation Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(key="stepTimeout", label="Step Timeout (seconds)", type="number", default=30),
            ParamField(key="confirmTimeout", label="Confirmation Timeout (seconds)", type="number", default=60),
            ParamField(key="cookiesFilename", label="Cookies Filename", type="text", default="microsoft-cookies.json", supportsTemplate=True),
            ParamField(key="resultVar", label="Result Variable (optional)", type="text", producesVariable=True),
        ],
        codegen=codegen_microsoft_login,
    )
)
