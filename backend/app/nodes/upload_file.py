from app.codegen.context import CodegenContext
from app.codegen.template_utils import render_template_expr, resolve_selector
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import selector_field, selector_type_field
from app.nodes.registry import register


def codegen_upload_file(ctx: CodegenContext) -> str:
    selector = resolve_selector(ctx)
    path_expr = render_template_expr(ctx.params.get("filePath", ""), ctx)
    return (
        f"{ctx.target_var}.locator({selector}).set_input_files({path_expr})\n"
        f'print(f"[{ctx.node_label}] uploaded " + {path_expr})'
    )


register(
    NodeSpec(
        type="upload_file",
        label="Upload File",
        category="action",
        description=(
            'Attaches a file to a file input (<input type="file">) identified by a selector — the '
            "counterpart to Fill Input for text fields. File Path is usually {{getFileNode.resultVar}} "
            "from a Get File node, or {{saveFilesNode.resultVar.files[0]}} straight from Save Files."
        ),
        icon="upload",
        params=[
            selector_field(placeholder="input[type=file]"),
            selector_type_field(),
            ParamField(
                key="filePath",
                label="File Path",
                type="text",
                required=True,
                supportsTemplate=True,
                consumesVariable=True,
            ),
        ],
        codegen=codegen_upload_file,
    )
)
