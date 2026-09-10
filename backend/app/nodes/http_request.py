from app.codegen.context import CodegenContext
from app.codegen.template_utils import render_template_expr, validate_identifier
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register

_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
_BODY_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_DEFAULT_TIMEOUT = 30


def _response_type(ctx: CodegenContext) -> str:
    return ctx.params.get("responseType") or "json"


def _auto_loop(ctx: CodegenContext) -> bool:
    if _response_type(ctx) == "base64":
        # A base64-encoded response body is one blob, not a list — nothing to loop
        # over, regardless of what the (hidden, in this mode) Loop automatically
        # toggle happens to be set to.
        return False
    value = ctx.params.get("autoLoop")
    return True if value is None else bool(value)


def _key_value_pairs(rows: object, ctx: CodegenContext) -> list[str]:
    pairs: list[str] = []
    if not isinstance(rows, list):
        return pairs
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (row.get("key") or "").strip()
        if not key:
            continue
        value_expr = render_template_expr(row.get("value", ""), ctx)
        pairs.append(f"{key!r}: {value_expr}")
    return pairs


def _headers_kwarg(ctx: CodegenContext) -> str | None:
    pairs = _key_value_pairs(ctx.params.get("headers"), ctx)
    if not pairs:
        return None
    return "headers={" + ", ".join(pairs) + "}"


def _timeout_kwarg(ctx: CodegenContext) -> str | None:
    """Every request gets a timeout by default (0 opts out) — without one, a slow or
    unresponsive API hangs the whole run forever instead of failing visibly."""
    value = ctx.params.get("timeoutSeconds")
    if value is None or value == "":
        value = _DEFAULT_TIMEOUT
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = _DEFAULT_TIMEOUT
    if seconds <= 0:
        return None
    return f"timeout={seconds:g}"


def _body_kwarg(ctx: CodegenContext, method: str) -> str | None:
    if method not in _BODY_METHODS:
        return None
    mode = ctx.params.get("bodyMode") or "json"
    if mode == "fields":
        pairs = _key_value_pairs(ctx.params.get("bodyFields"), ctx)
        if not pairs:
            return None
        return "json={" + ", ".join(pairs) + "}"

    body_raw = ctx.params.get("body")
    if not body_raw and method != "POST":
        return None
    body_expr = render_template_expr(body_raw or "{}", ctx)
    return f"json=json.loads({body_expr})"


def codegen_http_request(ctx: CodegenContext) -> str:
    params = ctx.params
    url_expr = render_template_expr(params.get("url", ""), ctx)
    method = str(params.get("method", "GET")).upper()
    if method not in _METHODS:
        method = "GET"

    call_kwargs = [
        kwarg for kwarg in (_headers_kwarg(ctx), _body_kwarg(ctx, method), _timeout_kwarg(ctx)) if kwarg
    ]
    kwargs_str = "".join(f", {kwarg}" for kwarg in call_kwargs)

    if _response_type(ctx) == "base64":
        # Raw response body (a file download — PDF, image, whatever), never parsed as
        # JSON — base64-encoded so it round-trips as a plain string, same as anything
        # else a template can reference (see Save Files, which expects exactly this:
        # a base64 string, never raw bytes, so it never has to guess which one it got).
        # A separate param key from `resultVar` (rather than reusing it) because
        # ParamField.visibleWhen only supports one sibling condition — resultVar's is
        # already "autoLoop is off", which doesn't combine with "responseType is
        # base64" (autoLoop is itself hidden/irrelevant in base64 mode).
        var_name = validate_identifier(params.get("base64Var"), ctx, "Result Variable")
        lines = [
            f"_resp = requests.{method.lower()}({url_expr}{kwargs_str})",
            f"{var_name} = base64.b64encode(_resp.content).decode('ascii')",
            f'print(f"[{ctx.node_label}] fetched {{len(_resp.content)}} byte(s), base64-encoded")',
        ]
        return "\n".join(lines)

    result_path = params.get("resultPath") or ""
    auto_loop = _auto_loop(ctx)

    lines = [f"_raw = requests.{method.lower()}({url_expr}{kwargs_str}).json()"]

    var_name = "data" if auto_loop else validate_identifier(params.get("resultVar"), ctx, "Result Variable")

    if result_path:
        lines.append(f"{var_name} = _dig(_raw, {result_path!r})")
    else:
        lines.append(f"{var_name} = _raw")

    lines.append(f'print(f"[{ctx.node_label}] fetched {{len({var_name})}} item(s)")')
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
                options=[{"value": m, "label": m} for m in _METHODS],
            ),
            ParamField(
                key="responseType",
                label="Response",
                type="select",
                default="json",
                options=[
                    {"value": "json", "label": "JSON"},
                    {"value": "base64", "label": "File (downloads the raw body, base64-encoded)"},
                ],
            ),
            ParamField(
                key="timeoutSeconds",
                label="Timeout (seconds, 0 = no timeout)",
                type="number",
                default=30,
                placeholder="30",
            ),
            ParamField(key="headers", label="Headers", type="keyValueList", default=[]),
            ParamField(
                key="bodyMode",
                label="Body",
                type="select",
                default="json",
                options=[{"value": "json", "label": "JSON"}, {"value": "fields", "label": "Key/Value Fields"}],
                visibleWhen={"key": "method", "in": list(_BODY_METHODS)},
            ),
            ParamField(
                key="body",
                label="Body (JSON)",
                type="textarea",
                placeholder='{"key": "value"}',
                visibleWhen={"key": "bodyMode", "equals": "json"},
            ),
            ParamField(
                key="bodyFields",
                label="Body Fields",
                type="keyValueList",
                default=[],
                visibleWhen={"key": "bodyMode", "equals": "fields"},
            ),
            ParamField(
                key="resultPath",
                label="Result Path (optional)",
                type="text",
                placeholder="results.items",
                visibleWhen={"key": "responseType", "equals": "json"},
            ),
            ParamField(
                key="autoLoop",
                label="Loop automatically over results",
                type="boolean",
                default=True,
                visibleWhen={"key": "responseType", "equals": "json"},
            ),
            ParamField(
                key="resultVar",
                label="Result Variable",
                type="text",
                placeholder="leads",
                producesVariable=True,
                visibleWhen=[{"key": "autoLoop", "equals": False}, {"key": "responseType", "equals": "json"}],
            ),
            ParamField(
                key="base64Var",
                label="Result Variable",
                type="text",
                placeholder="file_b64",
                producesVariable=True,
                visibleWhen={"key": "responseType", "equals": "base64"},
            ),
        ],
        codegen=codegen_http_request,
    )
)
