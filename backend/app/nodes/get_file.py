from app.codegen.context import CodegenContext, CodegenError
from app.codegen.template_utils import render_template_expr, validate_identifier
from app.config import temp_files_dir
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_get_file(ctx: CodegenContext) -> str:
    filename_raw = (ctx.params.get("filename") or "").strip()
    if not filename_raw:
        raise CodegenError(f"Node '{ctx.node_label}': 'Filename' is required")
    var = validate_identifier(ctx.params.get("resultVar"), ctx, "Result Variable")

    # Deliberately NOT tied to graph position (no edge to a specific Save Files node
    # required) — every node in a workflow shares the same temp_files/<workflow_id>/
    # folder, addressed by filename alone, so this can sit anywhere in the flow. See
    # the plan doc's design note: template refs only resolve to live Python variables
    # in scope, which doesn't work for "reference a file a non-adjacent node wrote" —
    # a deterministic on-disk path recomputed from project_id/workflow_id (both known
    # at codegen time) sidesteps that entirely.
    temp_dir_literal = repr(str(temp_files_dir(ctx.project_id, ctx.workflow_id)))
    filename_expr = render_template_expr(filename_raw, ctx)

    lines = [
        f"_filename = {filename_expr}",
        f"{var} = os.path.join({temp_dir_literal}, _filename)",
        f"if not os.path.exists({var}):",
        f"    raise FileNotFoundError('Get File: no file at ' + {var} + ' — make sure a Save Files node already "
        f"ran and wrote this filename earlier in this same run')",
        f'print(f"[{ctx.node_label}] {var} = " + {var})',
    ]
    return "\n".join(lines)


register(
    NodeSpec(
        type="get_file",
        label="Get File",
        category="action",
        description=(
            "Looks up a file by filename inside this workflow's temp_files folder (whatever a Save Files "
            "node already wrote earlier in this run) and stores its path in a variable — doesn't need to be "
            "connected to the Save Files node directly, can sit anywhere later in the flow. Feed the result "
            "into Upload File to attach it to a file input, or reference it in any templated field."
        ),
        icon="folder-open",
        params=[
            ParamField(
                key="filename",
                label="Filename",
                type="text",
                required=True,
                placeholder="documento.pdf",
                supportsTemplate=True,
            ),
            ParamField(
                key="resultVar",
                label="Result Variable",
                type="text",
                required=True,
                placeholder="filePath",
                producesVariable=True,
            ),
        ],
        codegen=codegen_get_file,
    )
)
