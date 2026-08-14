from app.codegen.context import CodegenContext, CodegenError
from app.codegen.template_utils import render_template_expr, resolve_credential_value, resolve_selector, validate_identifier
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import SELECTOR_TYPE_OPTIONS
from app.nodes.registry import register

_SITE_KEY_TYPES = {"recaptcha_v2", "recaptcha_v3", "hcaptcha", "turnstile", "funcaptcha"}


def codegen_two_captcha(ctx: CodegenContext) -> str:
    captcha_type = ctx.params.get("captchaType") or "recaptcha_v2"
    result_var = validate_identifier(ctx.params.get("resultVar"), ctx, "Result Variable")
    api_key_expr = resolve_credential_value(ctx, "credentialId", "2Captcha API Key")

    lines = [
        "from twocaptcha import TwoCaptcha",
        f"_solver = TwoCaptcha({api_key_expr})",
    ]

    # The solve call below blocks for as long as 2Captcha's own submit-and-poll cycle
    # takes — anywhere from a few seconds (image) to 15-90+ seconds (a human/AI worker
    # actually solving a reCAPTCHA/hCaptcha/etc). With no output in between, that looks
    # identical to a hung script, so log both ends of the wait explicitly.
    if captcha_type in _SITE_KEY_TYPES:
        site_key_raw = (ctx.params.get("siteKey") or "").strip()
        if not site_key_raw:
            raise CodegenError(f"Node '{ctx.node_label}': 'Site Key' is required")
        site_key_expr = render_template_expr(site_key_raw, ctx)

        lines.append(
            f'print("[{ctx.node_label}] submitting {captcha_type} to 2Captcha — this can take 15-90+ seconds '
            f'while a worker solves it, hang tight...")'
        )
        if captcha_type == "recaptcha_v3":
            action = (ctx.params.get("action") or "verify").strip()
            try:
                min_score = float(ctx.params.get("minScore") or 0.4)
            except (TypeError, ValueError):
                min_score = 0.4
            lines.append(
                f"_result = _solver.recaptcha(sitekey={site_key_expr}, url={ctx.target_var}.url, "
                f"version='v3', action={action!r}, score={min_score})"
            )
        elif captcha_type == "recaptcha_v2":
            lines.append(f"_result = _solver.recaptcha(sitekey={site_key_expr}, url={ctx.target_var}.url)")
        elif captcha_type == "hcaptcha":
            lines.append(f"_result = _solver.hcaptcha(sitekey={site_key_expr}, url={ctx.target_var}.url)")
        elif captcha_type == "turnstile":
            lines.append(f"_result = _solver.turnstile(sitekey={site_key_expr}, url={ctx.target_var}.url)")
        else:
            lines.append(f"_result = _solver.funcaptcha(sitekey={site_key_expr}, url={ctx.target_var}.url)")
    elif captcha_type == "image":
        selector = resolve_selector(ctx)
        lines.append(f'print("[{ctx.node_label}] capturing the captcha image...")')
        lines.append(f"_img_bytes = {ctx.target_var}.locator({selector}).screenshot()")
        lines.append("import base64 as _b64")
        lines.append(
            f'print("[{ctx.node_label}] submitting image to 2Captcha — this can take a few seconds to a '
            f'minute, hang tight...")'
        )
        lines.append("_result = _solver.normal(_b64.b64encode(_img_bytes).decode())")
    else:
        raise CodegenError(f"Node '{ctx.node_label}': unknown captcha type {captcha_type!r}")

    lines.append(f"{result_var} = _result['code']")
    lines.append(f'print(f"[{ctx.node_label}] captcha solved, {result_var} = " + {result_var})')

    # Getting the token is only half the job — most widgets check a hidden
    # <textarea>/<input name="..."> for the solved token (and often only react to a
    # real input/change event, not just the value being set), which is exactly the
    # step "solved but doesn't submit" usually means was missing. This targets the
    # standard field name for each widget; sites with a custom data-callback still
    # need that triggered separately (a Pause node + a pdb page.evaluate(...) is the
    # way to find and call it).
    if captcha_type in _SITE_KEY_TYPES and ctx.params.get("autoFillResponseField", True):
        js_source = (
            "(token) => {\n"
            "  const names = ['h-captcha-response', 'g-recaptcha-response', 'cf-turnstile-response'];\n"
            "  names.forEach((n) => {\n"
            '    document.querySelectorAll(`[name="${n}"]`).forEach((el) => {\n'
            "      el.value = token;\n"
            "      el.innerHTML = token;\n"
            "      el.dispatchEvent(new Event('input', { bubbles: true }));\n"
            "      el.dispatchEvent(new Event('change', { bubbles: true }));\n"
            "    });\n"
            "  });\n"
            "}"
        )
        lines.append(f"{ctx.target_var}.evaluate({js_source!r}, {result_var})")
        lines.append(f'print("[{ctx.node_label}] filled the response field on the page with the solved token")')

    return "\n".join(lines)


register(
    NodeSpec(
        type="two_captcha",
        label="2Captcha",
        category="function",
        description=(
            "Solves a captcha via the 2Captcha service and stores the answer/token in a "
            "variable — reCAPTCHA v2/v3, hCaptcha, Cloudflare Turnstile, and FunCaptcha use the "
            "page's current URL and a site key; Image captcha screenshots an element on the page "
            "and sends it for text recognition. Also fills the solved token into the page's own "
            "hidden response field (unless turned off) — some sites additionally require their "
            "own JS callback to be triggered before the form will actually submit; if the page "
            "still doesn't advance after this node, add a Pause node right after it to inspect "
            "what the widget expects. Requires a 2Captcha API key credential."
        ),
        icon="puzzle",
        params=[
            ParamField(
                key="credentialId",
                label="2Captcha API Key",
                type="text",
                required=True,
                credentialType="2captcha",
            ),
            ParamField(
                key="captchaType",
                label="Captcha Type",
                type="select",
                default="recaptcha_v2",
                options=[
                    {"value": "recaptcha_v2", "label": "reCAPTCHA v2"},
                    {"value": "recaptcha_v3", "label": "reCAPTCHA v3"},
                    {"value": "hcaptcha", "label": "hCaptcha"},
                    {"value": "turnstile", "label": "Cloudflare Turnstile"},
                    {"value": "funcaptcha", "label": "FunCaptcha"},
                    {"value": "image", "label": "Image (text) Captcha"},
                ],
            ),
            ParamField(
                key="siteKey",
                label="Site Key",
                type="text",
                supportsTemplate=True,
                placeholder="6Le...",
                visibleWhen={
                    "key": "captchaType",
                    "in": ["recaptcha_v2", "recaptcha_v3", "hcaptcha", "turnstile", "funcaptcha"],
                },
            ),
            ParamField(
                key="action",
                label="Action (reCAPTCHA v3)",
                type="text",
                default="verify",
                visibleWhen={"key": "captchaType", "equals": "recaptcha_v3"},
            ),
            ParamField(
                key="minScore",
                label="Minimum Score (reCAPTCHA v3)",
                type="number",
                default=0.4,
                visibleWhen={"key": "captchaType", "equals": "recaptcha_v3"},
            ),
            ParamField(
                key="selector",
                label="Image Selector Value",
                type="text",
                placeholder="e.g. #captcha-img, .captcha-image",
                visibleWhen={"key": "captchaType", "equals": "image"},
            ),
            ParamField(
                key="selectorType",
                label="Selector Type",
                type="select",
                default="css",
                options=SELECTOR_TYPE_OPTIONS,
                visibleWhen={"key": "captchaType", "equals": "image"},
            ),
            ParamField(
                key="autoFillResponseField",
                label="Auto-fill the page's hidden response field",
                type="boolean",
                default=True,
                visibleWhen={
                    "key": "captchaType",
                    "in": ["recaptcha_v2", "recaptcha_v3", "hcaptcha", "turnstile", "funcaptcha"],
                },
            ),
            ParamField(
                key="resultVar",
                label="Result Variable",
                type="text",
                required=True,
                placeholder="captcha_token",
                producesVariable=True,
            ),
        ],
        codegen=codegen_two_captcha,
    )
)
