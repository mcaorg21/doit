import re

from app.codegen.context import CodegenContext, CodegenError
from app.codegen.template_utils import render_template_expr, resolve_variable_operand, validate_identifier
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register

# A bare {{var}} or {{var.field}} with nothing else in the string — same shape
# template_utils.py's own (module-private) full-reference check uses. Matched here
# so a whole-value argument can pass through as the REAL Python value (dict, list,
# number, bool) via resolve_variable_operand, instead of always being stringified —
# render_template_expr (used for everything else) only ever produces a string.
_FULL_REF_RE = re.compile(r"^\{\{\s*[a-zA-Z_][a-zA-Z0-9_.]*\s*\}\}$")


def codegen_execute_script(ctx: CodegenContext) -> str:
    params = ctx.params
    script_raw = params.get("script")
    script_raw = script_raw.strip() if isinstance(script_raw, str) else ""
    if not script_raw:
        raise CodegenError(f"Node '{ctx.node_label}': 'Script' is required")

    # Wrapped as an arrow function taking one parameter named `arguments` — same
    # names/semantics as Selenium/ChromeDriver's execute_script(script, *args): the
    # script body references arguments[0], arguments[1], ... for whatever's passed
    # in below, and a `return` becomes this node's result. Built with plain string
    # concatenation (not an f-string) so the user's raw JS — full of its own {}
    # braces — never has to be escaped against Python's f-string syntax.
    js_code = "(arguments) => {\n" + script_raw + "\n}"

    rows = params.get("args") or []
    arg_exprs = []
    for i, raw in enumerate(rows):
        text_raw = (raw or "").strip() if isinstance(raw, str) else ""
        if not text_raw:
            raise CodegenError(f"Node '{ctx.node_label}': argument #{i + 1} is empty")
        if _FULL_REF_RE.match(text_raw):
            # The whole argument is one {{var}} reference — pass the real value
            # through (a dict/list/number/bool stays that type in JS too, since
            # Playwright JSON-serializes the args list), not a stringified copy.
            arg_exprs.append(resolve_variable_operand(text_raw, ctx, f"Argument #{i + 1}"))
        else:
            arg_exprs.append(render_template_expr(text_raw, ctx))
    args_list_expr = "[" + ", ".join(arg_exprs) + "]"

    # Always runs against the page itself, never a frame locator — same as
    # goto/open_browser/save_cookies: a script's `document`/`window` is a page-level
    # concept, not something Switch Frame's target_var should redirect.
    call_expr = f"page.evaluate({js_code!r}, {args_list_expr})"

    result_var_raw = (params.get("resultVar") or "").strip()
    if result_var_raw:
        var = validate_identifier(result_var_raw, ctx, "Result Variable")
        return f'{var} = {call_expr}\nprint(f"[{ctx.node_label}] {var} = " + str({var}))'
    return f'{call_expr}\nprint("[{ctx.node_label}] script executed")'


register(
    NodeSpec(
        type="execute_script",
        label="Execute Script (JS)",
        category="action",
        description=(
            "Runs raw JavaScript in the page — the same idea as Selenium/ChromeDriver's execute_script(): "
            "the script body can reference passed-in values as arguments[0], arguments[1], ... (see "
            "'Arguments' below), and a `return` statement becomes this node's result. Runs at the page level "
            "(document/window), not scoped to whatever Switch Frame is currently pointed at. The script text "
            "itself is NOT template-substituted — pass dynamic values in through Arguments instead of "
            "building the script as a string, so nothing you pass in can accidentally break the JS syntax."
        ),
        example="return document.title;  // resultVar gets the page's title",
        icon="code",
        params=[
            ParamField(
                key="script",
                label="Script",
                type="textarea",
                required=True,
                placeholder="return arguments[0] + arguments[1];",
            ),
            ParamField(
                key="args",
                label=(
                    "Arguments (optional — available inside the script as arguments[0], arguments[1], ...; a row "
                    "that is ONLY {{myVar}} passes the real value, not a stringified copy)"
                ),
                type="textList",
                default=[],
            ),
            ParamField(
                key="resultVar",
                label="Result Variable (optional — captures what the script returns)",
                type="text",
                placeholder="result",
                producesVariable=True,
            ),
        ],
        codegen=codegen_execute_script,
    )
)
