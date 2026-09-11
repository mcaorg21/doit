from app.codegen.context import CodegenContext
from app.codegen.template_utils import render_template_expr, resolve_selector, validate_identifier
from app.config import temp_files_dir
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import selector_field, selector_type_field
from app.nodes.registry import register

_DEFAULT_TIMEOUT_SECONDS = 300


def _timeout_seconds(ctx: CodegenContext) -> float:
    raw = ctx.params.get("timeout")
    try:
        seconds = float(raw) if raw not in (None, "") else _DEFAULT_TIMEOUT_SECONDS
    except (TypeError, ValueError):
        seconds = _DEFAULT_TIMEOUT_SECONDS
    return seconds if seconds > 0 else _DEFAULT_TIMEOUT_SECONDS


def _requested_name_lines(ctx: CodegenContext) -> list[str]:
    filename_raw = (ctx.params.get("filename") or "").strip()
    if filename_raw:
        return [f"_dl_requested_name = {render_template_expr(filename_raw, ctx)}"]
    return ["_dl_requested_name = download.suggested_filename"]


def _dl_dir_line(ctx: CodegenContext) -> str:
    # Absolute path up to the workflow baked in at codegen time; joined with
    # _PROCESS_ID (HEADER, one per script execution) at runtime, so two runs of the
    # same workflow firing at once never read/write each other's downloads.
    workflow_dir_literal = repr(str(temp_files_dir(ctx.project_id, ctx.workflow_id)))
    return f"_dl_dir = os.path.join({workflow_dir_literal}, _PROCESS_ID)"


def _tail_lines(ctx: CodegenContext, overwrite: bool) -> tuple[list[str], str | None]:
    lines = [
        "_dl_safe_name = _safe_download_filename(_dl_requested_name)",
        f"_dl_final_path = _unique_download_path(_dl_dir, _dl_safe_name, {overwrite!r})",
    ]
    result_var_raw = (ctx.params.get("resultVar") or "").strip()
    if result_var_raw:
        var = validate_identifier(result_var_raw, ctx, "Result Variable")
        assign = (
            f"{var} = {{'path': _dl_final_path, 'filename': os.path.basename(_dl_final_path), "
            "'suggestedFilename': download.suggested_filename}"
        )
    else:
        assign = None
    return lines, assign


def codegen_download_file(ctx: CodegenContext) -> str:
    """Real (non-demo) codegen — matches the with-block Playwright docs recommend for
    expect_download, since this is the version that runs for real (Run button,
    scheduled/webhook triggers) and there's no line-by-line pdb constraint here."""
    selector = resolve_selector(ctx)
    timeout_seconds = _timeout_seconds(ctx)
    overwrite = bool(ctx.params.get("overwrite", False))

    lines = [
        _dl_dir_line(ctx),
        "os.makedirs(_dl_dir, exist_ok=True)",
        f"with page.expect_download(timeout={timeout_seconds:g} * 1000) as download_info:",
        f"    {ctx.target_var}.locator({selector}).click()",
        "download = download_info.value",
        *_requested_name_lines(ctx),
    ]
    tail, assign = _tail_lines(ctx, overwrite)
    lines += tail
    # save_as wrapped in its own try/except so a failure partway through (disk full,
    # permission error, ...) doesn't leave a partial file behind — re-raised so the
    # engine's own outer try/except (added to every non-block-opening node) still
    # catches it and drops into the usual breakpoint() debugger.
    lines += [
        "try:",
        "    download.save_as(_dl_final_path)",
        "except Exception:",
        "    if os.path.exists(_dl_final_path):",
        "        os.remove(_dl_final_path)",
        "    raise",
    ]
    if assign:
        lines.append(assign)
    lines.append(f'print(f"[{ctx.node_label}] downloaded " + os.path.basename(_dl_final_path))')
    return "\n".join(lines)


def demo_codegen_download_file(ctx: CodegenContext) -> str:
    """Live-demo codegen — every line must be independently sendable to a paused pdb
    prompt one at a time (see app/mcp/live_sessions.py), which rules out the `with`
    block above (pdb's single-line REPL can't parse a `with X:` header without its
    body arriving as a separate command). page.expect_download() is a context
    manager, but its __enter__/__exit__ can be called by hand as two flat statements
    instead of a `with` block — same effect (the download listener is armed by
    __enter__ before the click, and __exit__ completes the wait), just restructured
    so nothing here is indented. No file-cleanup-on-failure try/except here either
    (unlike the real version above) — demo mode is inherently interactive, a failed
    save_as just surfaces as a normal captured error the caller can see and retry."""
    selector = resolve_selector(ctx)
    timeout_seconds = _timeout_seconds(ctx)
    overwrite = bool(ctx.params.get("overwrite", False))

    lines = [
        _dl_dir_line(ctx),
        "os.makedirs(_dl_dir, exist_ok=True)",
        f"_dl_ctx = page.expect_download(timeout={timeout_seconds:g} * 1000)",
        "_dl_info = _dl_ctx.__enter__()",
        f"{ctx.target_var}.locator({selector}).click()",
        "_ = _dl_ctx.__exit__(None, None, None)",
        "download = _dl_info.value",
        *_requested_name_lines(ctx),
    ]
    tail, assign = _tail_lines(ctx, overwrite)
    lines += tail
    lines.append("download.save_as(_dl_final_path)")
    if assign:
        lines.append(assign)
    # Deliberately basename-only (see app/mcp/server.py's demo_node docstring) — never
    # the full path, and never anything from the download itself (url/headers/etc.)
    # that could carry a session token or similar.
    lines.append(f'print("[{ctx.node_label}] downloaded " + os.path.basename(_dl_final_path))')
    return "\n".join(lines)


register(
    NodeSpec(
        type="download_file",
        label="Download File",
        category="action",
        description=(
            "Clicks an element that triggers a browser download, waits for it to finish, and saves it "
            "straight into this workflow's temp_files folder (never the system Downloads folder) — ready "
            "for Get File/Upload File elsewhere in the SAME run. Needs an open_browser earlier in the flow. "
            "Filename defaults to whatever the server suggested; set Filename to rename it. Never silently "
            "overwrites an existing file — appends a numbered suffix unless Overwrite is on. Each execution "
            "gets its own isolated subfolder, so two runs of this workflow firing at the same time (e.g. two "
            "webhook calls, or a scheduled run overlapping a manual one) never mix up each other's files."
        ),
        icon="download",
        params=[
            selector_field(placeholder="a.download-link, button#export"),
            selector_type_field(),
            ParamField(
                key="filename",
                label="Filename (optional — defaults to the server's suggested name)",
                type="text",
                supportsTemplate=True,
            ),
            ParamField(
                key="timeout",
                label="Timeout (seconds)",
                type="number",
                default=_DEFAULT_TIMEOUT_SECONDS,
                placeholder=str(_DEFAULT_TIMEOUT_SECONDS),
            ),
            ParamField(
                key="overwrite",
                label="Overwrite if a file with this name already exists",
                type="boolean",
                default=False,
            ),
            ParamField(
                key="resultVar",
                label="Result Variable (optional)",
                type="text",
                placeholder="downloaded",
                producesVariable=True,
            ),
        ],
        codegen=codegen_download_file,
        demo_codegen=demo_codegen_download_file,
    )
)
