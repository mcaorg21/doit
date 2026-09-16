from app.codegen.context import CodegenContext
from app.codegen.template_utils import (
    render_template_expr,
    resolve_credential_pair,
    resolve_credential_value,
    resolve_selector,
    validate_identifier,
)
from app.config import cookies_dir_for_credential
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import SELECTOR_TYPE_OPTIONS, fill_lines, typing_option_fields
from app.nodes.registry import register


def codegen_login(ctx: CodegenContext) -> str:
    params = ctx.params
    url_raw = (params.get("url") or "").strip()
    if not url_raw:
        from app.codegen.context import CodegenError

        raise CodegenError(f"Node '{ctx.node_label}': 'URL' is required")
    url_expr = render_template_expr(url_raw, ctx)

    login_expr, password_expr = resolve_credential_pair(ctx, "credentialId", "Login Credential")
    username_selector = resolve_selector(ctx, "usernameSelector", "usernameSelectorType")
    password_selector = resolve_selector(ctx, "passwordSelector", "passwordSelectorType")
    submit_selector = resolve_selector(ctx, "submitSelector", "submitSelectorType")
    confirm_selector = resolve_selector(ctx, "confirmSelector", "confirmSelectorType")

    try:
        confirm_timeout_ms = float(params.get("confirmTimeout") or 15) * 1000
    except (TypeError, ValueError):
        confirm_timeout_ms = 15000

    # Keyed by the credential (already validated above by resolve_credential_pair),
    # not by this workflow — any OTHER workflow using the same Login Credential shares
    # this same cookie jar, so logging in once lets every workflow that needs this
    # account skip the login form (a plain Load Cookies node pointed at the same
    # credential works too, see app/nodes/load_cookies.py).
    credential_id = (params.get("credentialId") or "").strip()
    cookies_dir_literal = repr(str(cookies_dir_for_credential(ctx.project_id, credential_id)))

    has_2fa = bool(params.get("has2FA"))
    clear_first = bool(params.get("clearFirst"))
    simulate_typing = bool(params.get("simulateTyping"))
    result_var_raw = (params.get("resultVar") or "").strip()
    var = validate_identifier(result_var_raw, ctx, "Result Variable") if result_var_raw else None

    lines = [
        f"_login_ck_dir = {cookies_dir_literal}",
        "_login_ck_path = os.path.join(_login_ck_dir, 'cookies.json')",
        "if os.path.exists(_login_ck_path):",
        "    _login_ck_data = json.loads(open(_login_ck_path, encoding='utf-8').read())",
        "    page.context.add_cookies(_login_ck_data)",
        f'    print(f"[{ctx.node_label}] loaded {{len(_login_ck_data)}} cookie(s), checking if still logged in...")',
        f"page.goto({url_expr})",
        "_login_already_ok = False",
        "try:",
        f"    page.locator({confirm_selector}).wait_for(timeout={confirm_timeout_ms:g})",
        "    _login_already_ok = True",
        f'    print("[{ctx.node_label}] already logged in (cookie session still valid) — skipping the login form")',
        "except Exception:",
        "    pass",
        "if not _login_already_ok:",
        f'    print("[{ctx.node_label}] not logged in — filling the login form")',
        *(f"    {line}" for line in fill_lines(f"page.locator({username_selector})", login_expr, clear_first, simulate_typing)),
        *(f"    {line}" for line in fill_lines(f"page.locator({password_selector})", password_expr, clear_first, simulate_typing)),
        f"    page.locator({submit_selector}).click()",
    ]

    if has_2fa:
        totp_secret_expr = resolve_credential_value(ctx, "totpCredentialId", "2FA Secret")
        code_selector = resolve_selector(ctx, "twoFaCodeSelector", "twoFaCodeSelectorType")
        lines += [
            "    import pyotp",
            f"    _login_totp_code = pyotp.TOTP({totp_secret_expr}).now()",
            *(f"    {line}" for line in fill_lines(f"page.locator({code_selector})", "_login_totp_code", clear_first, simulate_typing)),
        ]
        two_fa_submit_raw = (params.get("twoFaSubmitSelector") or "").strip()
        if two_fa_submit_raw:
            two_fa_submit_selector = resolve_selector(ctx, "twoFaSubmitSelector", "twoFaSubmitSelectorType")
            lines.append(f"    page.locator({two_fa_submit_selector}).click()")

    lines += [
        f"    page.locator({confirm_selector}).wait_for(timeout={confirm_timeout_ms:g})",
        f'    print("[{ctx.node_label}] login confirmed")',
        "    _login_ck_data = page.context.cookies()",
        "    os.makedirs(_login_ck_dir, exist_ok=True)",
        "    open(_login_ck_path, 'w', encoding='utf-8').write(json.dumps(_login_ck_data))",
        f'    print(f"[{ctx.node_label}] saved {{len(_login_ck_data)}} cookie(s) for next run")',
    ]

    if var:
        lines.append(f"{var} = {{'alreadyLoggedIn': _login_already_ok}}")

    return "\n".join(lines)


register(
    NodeSpec(
        type="login",
        label="Login",
        category="browser",
        description=(
            "A complete login flow in one node: loads any cookies saved from a previous run first and checks "
            "whether the confirmation element is already there (skips the form entirely if so); otherwise "
            "fills username/password from a credential, submits, optionally handles a TOTP 2FA step, waits "
            "for the confirmation element to prove it worked, then saves fresh cookies for next time. Needs "
            "an open_browser earlier in the flow. Doesn't handle captchas — if the login form has one, add a "
            "2Captcha node between filling the password and clicking submit. The cookie jar is tied to the "
            "Login Credential itself (not to this workflow) — any other workflow using the same credential, "
            "via its own Login node or a Save Cookies/Load Cookies node pointed at that credential, shares "
            "the same saved session."
        ),
        example='Logs into https://app.example.com using a stored credential, then saves the session',
        icon="log-in",
        params=[
            ParamField(
                key="url",
                label="Login Page URL",
                type="text",
                required=True,
                supportsTemplate=True,
                placeholder="https://example.com/login",
            ),
            ParamField(
                key="credentialId",
                label="Login Credential (username + password)",
                type="text",
                required=True,
                credentialType="login",
            ),
            ParamField(key="usernameSelector", label="Username Field Selector", type="text", required=True, placeholder="#email"),
            ParamField(key="usernameSelectorType", label="Username Field Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(key="passwordSelector", label="Password Field Selector", type="text", required=True, placeholder="#password"),
            ParamField(key="passwordSelectorType", label="Password Field Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(key="submitSelector", label="Submit Button Selector", type="text", required=True, placeholder="button[type=submit]"),
            ParamField(key="submitSelectorType", label="Submit Button Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(
                key="confirmSelector",
                label="Logged-in Confirmation Selector",
                type="text",
                required=True,
                placeholder="e.g. #logout-button, .user-avatar — something only visible once logged in",
            ),
            ParamField(key="confirmSelectorType", label="Confirmation Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS),
            ParamField(
                key="confirmTimeout",
                label="Confirmation Timeout (seconds)",
                type="number",
                default=15,
                placeholder="15",
            ),
            *typing_option_fields(),
            ParamField(key="has2FA", label="Site has TOTP 2FA", type="boolean", default=False),
            ParamField(
                key="totpCredentialId",
                label="2FA Secret (T2FA_SECRET)",
                type="text",
                credentialType="totp",
                visibleWhen={"key": "has2FA", "equals": True},
            ),
            ParamField(
                key="twoFaCodeSelector",
                label="2FA Code Field Selector",
                type="text",
                placeholder="#totp-code",
                visibleWhen={"key": "has2FA", "equals": True},
            ),
            ParamField(
                key="twoFaCodeSelectorType",
                label="2FA Code Field Selector Type",
                type="select",
                default="css",
                options=SELECTOR_TYPE_OPTIONS,
                visibleWhen={"key": "has2FA", "equals": True},
            ),
            ParamField(
                key="twoFaSubmitSelector",
                label="2FA Submit Button Selector (optional — leave empty if the form auto-submits)",
                type="text",
                placeholder="button[type=submit]",
                visibleWhen={"key": "has2FA", "equals": True},
            ),
            ParamField(
                key="twoFaSubmitSelectorType",
                label="2FA Submit Button Selector Type",
                type="select",
                default="css",
                options=SELECTOR_TYPE_OPTIONS,
                visibleWhen={"key": "has2FA", "equals": True},
            ),
            ParamField(
                key="resultVar",
                label="Result Variable (optional)",
                type="text",
                placeholder="loginResult",
                producesVariable=True,
            ),
        ],
        codegen=codegen_login,
    )
)
