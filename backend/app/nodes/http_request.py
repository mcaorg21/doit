from app.codegen.context import CodegenContext
from app.codegen.template_utils import render_template_expr
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_http_request(ctx: CodegenContext) -> str:
    params = ctx.params
    url_expr = render_template_expr(params.get("url", ""), ctx)
    method = str(params.get("method", "GET")).upper()
    result_path = params.get("resultPath") or ""

    lines = []
    if method == "POST":
        body_expr = render_template_expr(params.get("body") or "{}", ctx)
        lines.append(f"_raw = requests.post({url_expr}, json=json.loads({body_expr})).json()")
    else:
        lines.append(f"_raw = requests.get({url_expr}).json()")

    if result_path:
        lines.append(f"data = _dig(_raw, {result_path!r})")
    else:
        lines.append("data = _raw")

    lines.append(f'print(f"[{ctx.node_id}] fetched {{len(data)}} item(s)")')
    lines.append("for item in data:")
    return "\n".join(lines)


register(
    NodeSpec(
        type="http_request",
        label="HTTP Request",
        category="dataSource",
        description="Fetches a list of records that drive one loop iteration each for the rest of the workflow.",
        icon="globe",
        opens_block=True,
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
        ],
        codegen=codegen_http_request,
    )
)
