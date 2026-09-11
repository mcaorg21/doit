from app.codegen.context import CodegenContext, CodegenError
from app.codegen.template_utils import render_template_expr, validate_identifier
from app.config import temp_files_dir
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register

_MERGE_FORMATS = ("zip", "pdf")


def codegen_save_files(ctx: CodegenContext) -> str:
    rows = ctx.params.get("files") or []
    if not isinstance(rows, list) or not rows:
        raise CodegenError(f"Node '{ctx.node_label}': add at least one file")

    # Absolute path baked in at codegen time (the backend process, which has
    # app.config available) — the generated script runs standalone and never
    # imports app.config itself, see app/execution/runner.py. Joined with
    # _PROCESS_ID (HEADER) at runtime, not baked in here — that id doesn't exist
    # until the script actually starts, one per execution, see HEADER's own comment.
    workflow_dir_literal = repr(str(temp_files_dir(ctx.project_id, ctx.workflow_id)))

    lines = [
        f"_temp_dir = os.path.join({workflow_dir_literal}, _PROCESS_ID)",
        "os.makedirs(_temp_dir, exist_ok=True)",
        "_saved_files = []",
    ]

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise CodegenError(f"Node '{ctx.node_label}': file #{i + 1} is invalid")
        filename_raw = (row.get("filename") or "").strip()
        if not filename_raw:
            raise CodegenError(f"Node '{ctx.node_label}': file #{i + 1} is missing a filename")
        value_raw = row.get("value") or ""
        if not value_raw.strip():
            raise CodegenError(f"Node '{ctx.node_label}': file #{i + 1} ('{filename_raw}') is missing its content")

        filename_expr = render_template_expr(filename_raw, ctx)
        value_expr = render_template_expr(value_raw, ctx)
        # Base64 in, always — the same contract HTTP Request's "File" response mode
        # produces, so this node never has to guess whether it received raw bytes or
        # an encoded string (see http_request.py's _response_type).
        lines.append(f"_filename_{i} = {filename_expr}")
        lines.append(f"_path_{i} = os.path.join(_temp_dir, _filename_{i})")
        lines.append(f"with open(_path_{i}, 'wb') as _f_{i}:")
        lines.append(f"    _f_{i}.write(base64.b64decode({value_expr}))")
        lines.append(f"_saved_files.append(_path_{i})")

    lines.append(f'print(f"[{ctx.node_label}] saved {{len(_saved_files)}} file(s) to " + _temp_dir)')

    merged_var_expr = "None"
    if ctx.params.get("merge"):
        merged_filename_raw = (ctx.params.get("mergedFilename") or "").strip()
        if not merged_filename_raw:
            raise CodegenError(f"Node '{ctx.node_label}': set a filename for the merged file")
        merge_format = ctx.params.get("mergeFormat") or "zip"
        if merge_format not in _MERGE_FORMATS:
            merge_format = "zip"

        merged_filename_expr = render_template_expr(merged_filename_raw, ctx)
        lines.append(f"_merged_filename = {merged_filename_expr}")
        lines.append("_merged_path = os.path.join(_temp_dir, _merged_filename)")
        if merge_format == "pdf":
            lines += [
                "from pypdf import PdfWriter",
                "_pdf_writer = PdfWriter()",
                "for _p in _saved_files:",
                "    _pdf_writer.append(_p)",
                "with open(_merged_path, 'wb') as _mf:",
                "    _pdf_writer.write(_mf)",
            ]
        else:
            lines += [
                "import zipfile",
                "with zipfile.ZipFile(_merged_path, 'w') as _zf:",
                "    for _p in _saved_files:",
                "        _zf.write(_p, os.path.basename(_p))",
            ]
        lines.append(f'print(f"[{ctx.node_label}] merged into " + _merged_path)')
        merged_var_expr = "_merged_path"

    result_var_raw = (ctx.params.get("resultVar") or "").strip()
    if result_var_raw:
        var = validate_identifier(result_var_raw, ctx, "Result Variable")
        lines.append(f"{var} = {{'files': _saved_files, 'merged': {merged_var_expr}}}")

    return "\n".join(lines)


register(
    NodeSpec(
        type="save_files",
        label="Save Files",
        category="action",
        description=(
            "Decodes one or more base64 values (typically an HTTP Request node's \"File\" response) and "
            "writes them to data/projects/<project>/temp_files/<this workflow>/<this run>/<filename> — each "
            "execution gets its own isolated subfolder, so two runs firing at the same time never mix up "
            "each other's files. Can optionally merge everything saved into one final file (zip or PDF) in "
            "the same folder. Use Get File anywhere else in the SAME run to retrieve what was saved here by "
            "filename."
        ),
        icon="save",
        params=[
            ParamField(key="files", label="Files", type="fileList", default=[]),
            ParamField(key="merge", label="Merge into one final file", type="boolean", default=False),
            ParamField(
                key="mergeFormat",
                label="Merge Format",
                type="select",
                default="zip",
                options=[
                    {"value": "zip", "label": "ZIP (works for any file type)"},
                    {"value": "pdf", "label": "PDF (combines PDF pages into one PDF)"},
                ],
                visibleWhen={"key": "merge", "equals": True},
            ),
            ParamField(
                key="mergedFilename",
                label="Merged Filename",
                type="text",
                placeholder="merged.zip",
                supportsTemplate=True,
                visibleWhen={"key": "merge", "equals": True},
            ),
            ParamField(
                key="resultVar",
                label="Result Variable (optional)",
                type="text",
                placeholder="savedFiles",
                producesVariable=True,
            ),
        ],
        codegen=codegen_save_files,
    )
)
