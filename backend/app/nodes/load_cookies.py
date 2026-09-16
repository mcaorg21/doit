from app.codegen.context import CodegenContext
from app.codegen.template_utils import render_template_expr, validate_identifier
from app.config import cookies_dir, cookies_dir_for_credential
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_load_cookies(ctx: CodegenContext) -> str:
    credential_id = (ctx.params.get("credentialId") or "").strip()
    if credential_id:
        # Shared with Login/Microsoft Login (and Save Cookies) pointed at the same
        # credential — reads whatever session any of those last saved for it,
        # regardless of which workflow saved it. The filename param is ignored here.
        cookies_dir_literal = repr(str(cookies_dir_for_credential(ctx.project_id, credential_id)))
        path_expr = "os.path.join(_ck_dir, 'cookies.json')"
    else:
        cookies_dir_literal = repr(str(cookies_dir(ctx.project_id, ctx.workflow_id)))
        filename_raw = (ctx.params.get("filename") or "cookies.json").strip() or "cookies.json"
        filename_expr = render_template_expr(filename_raw, ctx)
        path_expr = f"os.path.join(_ck_dir, {filename_expr})"
    skip_if_missing = bool(ctx.params.get("skipIfMissing", True))

    result_var_raw = (ctx.params.get("resultVar") or "").strip()
    var = validate_identifier(result_var_raw, ctx, "Result Variable") if result_var_raw else None

    lines = [
        f"_ck_dir = {cookies_dir_literal}",
        f"_ck_path = {path_expr}",
        "if os.path.exists(_ck_path):",
        "    _ck_data = json.loads(open(_ck_path, encoding='utf-8').read())",
        "    page.context.add_cookies(_ck_data)",
        f'    print(f"[{ctx.node_label}] loaded {{len(_ck_data)}} cookie(s) from " + _ck_path)',
    ]
    if var:
        lines.append(f"    {var} = {{'path': _ck_path, 'count': len(_ck_data), 'loaded': True}}")

    if skip_if_missing:
        lines.append("else:")
        lines.append(f'    print(f"[{ctx.node_label}] no cookies file at " + _ck_path + " — skipping")')
        if var:
            lines.append(f"    {var} = {{'path': _ck_path, 'count': 0, 'loaded': False}}")
    else:
        lines.append("else:")
        lines.append(
            "    raise FileNotFoundError('Load Cookies: no file at ' + _ck_path + ' — run a Save Cookies "
            "node first, or turn on \"Skip if missing\"')"
        )

    return "\n".join(lines)


register(
    NodeSpec(
        type="load_cookies",
        label="Load Cookies",
        category="browser",
        description=(
            "Loads cookies previously written by a Save Cookies node, or by a Login/Microsoft Login node, "
            "into the current browser context — place it right after open_browser and before navigating, so "
            "the site sees the session cookies on its first request. On the very first run (no cookies file "
            "yet) it just skips loading and logs it, unless \"Skip if missing\" is turned off. Needs an "
            "open_browser earlier in the flow. Pick a Credential to load the shared jar a Login/Microsoft "
            "Login node (or another workflow's Save Cookies) saved for that credential — this is what lets a "
            "DIFFERENT workflow reuse a session without its own Login node. Leave it empty to load from this "
            "workflow's own jar by filename instead, same as before."
        ),
        example="Loads a previously saved session, shared by credential or scoped to this workflow",
        icon="cookie",
        params=[
            ParamField(
                key="credentialId",
                label="Credential (optional — loads the jar a Login node using this same credential saved)",
                type="text",
                credentialType="login",
            ),
            ParamField(
                key="filename",
                label="Filename (ignored when a Credential is selected)",
                type="text",
                default="cookies.json",
                placeholder="cookies.json",
                supportsTemplate=True,
            ),
            ParamField(
                key="skipIfMissing",
                label="Skip if missing (don't error when there's no saved cookies file yet)",
                type="boolean",
                default=True,
            ),
            ParamField(
                key="resultVar",
                label="Result Variable (optional)",
                type="text",
                placeholder="loadedCookies",
                producesVariable=True,
            ),
        ],
        codegen=codegen_load_cookies,
    )
)
