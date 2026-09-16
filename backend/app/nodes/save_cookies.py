from app.codegen.context import CodegenContext
from app.codegen.template_utils import render_template_expr, validate_identifier
from app.config import cookies_dir, cookies_dir_for_credential
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_save_cookies(ctx: CodegenContext) -> str:
    # Absolute path baked in at codegen time (the backend process, which has
    # app.config available) — the generated script runs standalone and never
    # imports app.config itself, see app/execution/runner.py. Unlike Save Files'
    # temp_files_dir, this is NOT nested under _PROCESS_ID: cookies are meant to
    # persist across runs (skip the login flow next time), not stay isolated to one.
    credential_id = (ctx.params.get("credentialId") or "").strip()
    if credential_id:
        # Shared with Login/Microsoft Login (and Load Cookies) pointed at the same
        # credential — any workflow can write into that shared jar. The filename
        # param is ignored here: one jar per credential, no name to pick.
        cookies_dir_literal = repr(str(cookies_dir_for_credential(ctx.project_id, credential_id)))
        path_expr = "os.path.join(_ck_dir, 'cookies.json')"
    else:
        cookies_dir_literal = repr(str(cookies_dir(ctx.project_id, ctx.workflow_id)))
        filename_raw = (ctx.params.get("filename") or "cookies.json").strip() or "cookies.json"
        filename_expr = render_template_expr(filename_raw, ctx)
        path_expr = f"os.path.join(_ck_dir, {filename_expr})"

    lines = [
        "_ck_data = page.context.cookies()",
        f"_ck_dir = {cookies_dir_literal}",
        "os.makedirs(_ck_dir, exist_ok=True)",
        f"_ck_path = {path_expr}",
        "open(_ck_path, 'w', encoding='utf-8').write(json.dumps(_ck_data))",
        f'print(f"[{ctx.node_label}] saved {{len(_ck_data)}} cookie(s) to " + _ck_path)',
    ]

    result_var_raw = (ctx.params.get("resultVar") or "").strip()
    if result_var_raw:
        var = validate_identifier(result_var_raw, ctx, "Result Variable")
        lines.append(f"{var} = {{'path': _ck_path, 'count': len(_ck_data)}}")

    return "\n".join(lines)


register(
    NodeSpec(
        type="save_cookies",
        label="Save Cookies",
        category="browser",
        description=(
            "Saves the current browser context's cookies (login sessions, etc.) — persists across runs, so a "
            "later Load Cookies node (in this run or a future one) can skip the login flow entirely. Needs an "
            "open_browser earlier in the flow. Unlike Save Files/Download File, this is NOT isolated per "
            "run — saving overwrites whatever was there before, by design. Pick a Credential to save into the "
            "SAME shared jar a Login/Microsoft Login node (or another workflow's Save Cookies) uses for that "
            "credential — any other workflow can then load it via Load Cookies pointed at the same credential. "
            "Leave it empty to save to this workflow's own jar by filename instead, same as before."
        ),
        example="Saves the current login session's cookies, shared by credential or scoped to this workflow",
        icon="cookie",
        params=[
            ParamField(
                key="credentialId",
                label="Credential (optional — shares the jar with a Login node using this same credential)",
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
                key="resultVar",
                label="Result Variable (optional)",
                type="text",
                placeholder="savedCookies",
                producesVariable=True,
            ),
        ],
        codegen=codegen_save_cookies,
    )
)
