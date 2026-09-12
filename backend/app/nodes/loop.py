from app.codegen.context import CodegenContext
from app.codegen.template_utils import validate_identifier, validate_json_array
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_loop(ctx: CodegenContext) -> str:
    if ctx.params.get("sourceType") == "variable":
        var = validate_identifier(ctx.params.get("arrayVar", ""), ctx, "Array Variable")
        lines = [f"data = {var}"]
    else:
        raw = ctx.params.get("arrayJson") or "[]"
        validate_json_array(raw, ctx, "Array (JSON)")
        lines = [f"data = json.loads({raw!r})"]

    lines.append(f'print(f"[{ctx.node_label}] looping over {{len(data)}} item(s)")')
    lines.append("for item in data:")
    return "\n".join(lines)


register(
    NodeSpec(
        type="loop",
        label="Loop",
        category="dataSource",
        description=(
            "Iterates over an array — typed in directly as JSON, or read from a variable "
            "set by an earlier node — running everything downstream once per item, "
            "accessible as {{item.field}} (same mechanism as HTTP Request's loop)."
        ),
        example='Loops over {{leads}}, running the nodes inside once per item',
        icon="repeat",
        opens_block=True,
        params=[
            ParamField(
                key="sourceType",
                label="Array Source",
                type="select",
                default="literal",
                options=[
                    {"value": "literal", "label": "JSON typed in"},
                    {"value": "variable", "label": "Variable from earlier node"},
                ],
            ),
            ParamField(
                key="arrayJson",
                label="Array (JSON)",
                type="textarea",
                placeholder='["a@x.com", "b@x.com"]  or  [{"name": "Alice"}, {"name": "Bob"}]',
                visibleWhen={"key": "sourceType", "equals": "literal"},
            ),
            ParamField(
                key="arrayVar",
                label="Array Variable",
                type="text",
                placeholder="my_list",
                consumesVariable=True,
                visibleWhen={"key": "sourceType", "equals": "variable"},
            ),
        ],
        codegen=codegen_loop,
    )
)
