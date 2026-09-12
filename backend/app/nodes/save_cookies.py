from app.codegen.context import CodegenContext
from app.codegen.template_utils import render_template_expr, validate_identifier
from app.config import cookies_dir
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_save_cookies(ctx: CodegenContext) -> str:
    # Absolute path baked in at codegen time (the backend process, which has
    # app.config available) — the generated script runs standalone and never
    # imports app.config itself, see app/execution/runner.py. Unlike Save Files'
    # temp_files_dir, this is NOT nested under _PROCESS_ID: cookies are meant to
    # persist across runs (skip the login flow next time), not stay isolated to one.
    cookies_dir_literal = repr(str(cookies_dir(ctx.project_id, ctx.workflow_id)))
    filename_raw = (ctx.params.get("filename") or "cookies.json").strip() or "cookies.json"
    filename_expr = render_template_expr(filename_raw, ctx)

    lines = [
        "_ck_data = page.context.cookies()",
        f"_ck_dir = {cookies_dir_literal}",
        "os.makedirs(_ck_dir, exist_ok=True)",
        f"_ck_path = os.path.join(_ck_dir, {filename_expr})",
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
            "Saves the current browser context's cookies (login sessions, etc.) to "
            "data/projects/<project>/cookies/<this workflow>/<filename> — persists across runs, so a later "
            "Load Cookies node (in this run or a future one) can skip the login flow entirely. Needs an "
            "open_browser earlier in the flow. Unlike Save Files/Download File, this is NOT isolated per "
            "run — saving overwrites whatever was there before, by design."
        ),
        example="Saves the current login session's cookies to 'cookies.json'",
        icon="cookie",
        params=[
            ParamField(
                key="filename",
                label="Filename",
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
