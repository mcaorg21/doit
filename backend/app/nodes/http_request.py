from app.codegen.context import CodegenContext
from app.codegen.template_utils import render_template_expr, validate_identifier
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def _auto_loop(ctx: CodegenContext) -> bool:
    value = ctx.params.get("autoLoop")
    return True if value is None else bool(value)


def codegen_http_request(ctx: CodegenContext) -> str:
    params = ctx.params
    url_expr = render_template_expr(params.get("url", ""), ctx)
    method = str(params.get("method", "GET")).upper()
    result_path = params.get("resultPath") or ""
    auto_loop = _auto_loop(ctx)

    lines = []
    if method == "POST":
        body_expr = render_template_expr(params.get("body") or "{}", ctx)
        lines.append(f"_raw = requests.post({url_expr}, json=json.loads({body_expr})).json()")
    else:
        lines.append(f"_raw = requests.get({url_expr}).json()")

    var_name = "data" if auto_loop else validate_identifier(params.get("resultVar"), ctx, "Result Variable")

    if result_path:
        lines.append(f"{var_name} = _dig(_raw, {result_path!r})")
    else:
        lines.append(f"{var_name} = _raw")

    lines.append(f'print(f"[{ctx.node_id}] fetched {{len({var_name})}} item(s)")')
    if auto_loop:
        lines.append("for item in data:")
    return "\n".join(lines)


register(
    NodeSpec(
        type="http_request",
        label="HTTP Request",
        category="dataSource",
        description=(
            "Fetches data from an API. By default it loops over the result directly "
            '(one iteration per item); turn off "Loop automatically" to instead store '
            "the fetched data in a named variable for a separate Loop node to pick up "
            "and iterate later."
        ),
        icon="globe",
        opens_block=_auto_loop,
        params=[
            ParamField(key="url", label="URL", type="text", required=True, placeholder="https://api.example.com/leads"),
            ParamField(
                key="method",
                label="Method",
                type="select",
                default="GET",
                options=[{"value": "GET", "label": "GET"}, {"value": "POST", "label": "POST"}],
            ),
            ParamField(key="body", label="Body (JSON, for POST)", type="textarea"),
            ParamField(
                key="resultPath",
                label="Result Path (optional)",
                type="text",
                placeholder="results.items",
            ),
            ParamField(key="autoLoop", label="Loop automatically over results", type="boolean", default=True),
            ParamField(
                key="resultVar",
                label="Result Variable",
                type="text",
                placeholder="leads",
                producesVariable=True,
                visibleWhen={"key": "autoLoop", "equals": False},
            ),
        ],
        codegen=codegen_http_request,
    )
)
