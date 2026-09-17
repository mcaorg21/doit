from app.codegen.context import CodegenContext, CodegenError
from app.codegen.template_utils import resolve_condition_operand, resolve_selector, validate_identifier
from app.nodes.base import NodeSpec, ParamField
from app.nodes.common import selector_field, selector_type_field, timeout_field, timeout_ms_kwarg
from app.nodes.registry import register

# Same shape as the IF node's operator table (app/nodes/if_node.py), trimmed to the
# operators that make sense against a single extracted string (the element's text or
# one attribute) — no exists/notExists here, since presence is already handled by the
# "Just Presence" check mode before an operator ever runs.
_TEXT_OPS = [
    ("equal", "Is Equal To"),
    ("notEqual", "Is Not Equal To"),
    ("contains", "Contains"),
    ("notContains", "Does Not Contain"),
    ("startsWith", "Starts With"),
    ("notStartsWith", "Does Not Start With"),
    ("endsWith", "Ends With"),
    ("notEndsWith", "Does Not End With"),
    ("regex", "Matches Regex"),
    ("notRegex", "Does Not Match Regex"),
    ("empty", "Is Empty"),
    ("notEmpty", "Is Not Empty"),
]
_UNARY_OPS = {"empty", "notEmpty"}
_BINARY_OPS = [code for code, _ in _TEXT_OPS if code not in _UNARY_OPS]

# _is_empty/_regex_match are defined once in engine.py's HEADER (shared with the IF
# node) — reused here instead of duplicated.
_TEXT_EXPR = {
    "equal": lambda l, r: f"(({l}) == ({r}))",
    "notEqual": lambda l, r: f"(({l}) != ({r}))",
    "contains": lambda l, r: f"(({r}) in ({l} or ''))",
    "notContains": lambda l, r: f"(({r}) not in ({l} or ''))",
    "startsWith": lambda l, r: f"(({l} or '').startswith({r}))",
    "notStartsWith": lambda l, r: f"(not ({l} or '').startswith({r}))",
    "endsWith": lambda l, r: f"(({l} or '').endswith({r}))",
    "notEndsWith": lambda l, r: f"(not ({l} or '').endswith({r}))",
    "regex": lambda l, r: f"_regex_match({l}, {r})",
    "notRegex": lambda l, r: f"(not _regex_match({l}, {r}))",
    "empty": lambda l, r: f"_is_empty({l})",
    "notEmpty": lambda l, r: f"(not _is_empty({l}))",
}


def codegen_element_if(ctx: CodegenContext) -> str:
    selector = resolve_selector(ctx)
    timeout_ms = timeout_ms_kwarg(ctx.params, default_seconds=5)
    check_mode = ctx.params.get("checkMode") or "presence"

    result_var = (ctx.params.get("resultVar") or "").strip()
    if result_var:
        result_var = validate_identifier(result_var, ctx, "Result Variable")

    loc_var = f"_el_{ctx.node_id}"
    present_var = f"_present_{ctx.node_id}"

    lines = [
        f"{loc_var} = {ctx.target_var}.locator({selector})",
        "try:",
        f"    {loc_var}.first.wait_for(state='attached', {timeout_ms})",
        "except Exception:",
        "    pass",
        f"{present_var} = {loc_var}.count() > 0",
        f'print(f"[{ctx.node_label}] present = " + str({present_var}))',
    ]

    if check_mode == "presence":
        condition_expr = present_var
        if result_var:
            lines.append(f"{result_var} = {present_var}")
    else:
        operator = ctx.params.get("operator") or "contains"
        valid_ops = {code for code, _ in _TEXT_OPS}
        if operator not in valid_ops:
            raise CodegenError(f"Node '{ctx.node_label}': operator {operator!r} is not valid")

        if check_mode == "text":
            extract = f"{loc_var}.first.inner_text()"
        elif check_mode == "attribute":
            attr_name = (ctx.params.get("attributeName") or "").strip()
            if not attr_name:
                raise CodegenError(f"Node '{ctx.node_label}': 'Attribute Name' is required when checking an attribute")
            extract = f"{loc_var}.first.get_attribute({attr_name!r})"
        else:
            raise CodegenError(f"Node '{ctx.node_label}': unknown Check mode {check_mode!r}")

        value_var = f"_val_{ctx.node_id}"
        lines.append(f"{value_var} = (({extract}) if {present_var} else None)")
        lines.append(f'print(f"[{ctx.node_label}] value = " + str({value_var}))')
        if result_var:
            lines.append(f"{result_var} = {value_var}")

        right = None
        if operator not in _UNARY_OPS:
            right = resolve_condition_operand(ctx.params.get("value"), ctx, "Value", literal_kind="string")
        builder = _TEXT_EXPR[operator]
        condition_expr = f"({present_var} and {builder(value_var, right)})"

    lines.append(f"if {condition_expr}:")
    return "\n".join(lines)


register(
    NodeSpec(
        type="element_if",
        label="Element Condition",
        category="logic",
        description=(
            "Fuses 'Element Present?' and 'IF' into one step: looks for an element and, only if it's "
            "there, immediately checks a condition on it (its text or one attribute) — the true branch "
            "only fires when both the element exists AND the condition matches. Saves having to chain a "
            "separate Element Present? into an IF just to check something about what was found."
        ),
        example="If '.status-badge' is present and its text contains 'Aprovado', branch true, otherwise false",
        icon="search-check",
        opens_block=True,
        is_branch=True,
        params=[
            selector_field(placeholder="#status, .badge, //div[@class='alert']"),
            selector_type_field(),
            timeout_field(default_seconds=5),
            ParamField(
                key="checkMode",
                label="Check",
                type="select",
                default="presence",
                options=[
                    {"value": "presence", "label": "Just Presence (found / not found)"},
                    {"value": "text", "label": "Its Text"},
                    {"value": "attribute", "label": "An Attribute"},
                ],
            ),
            ParamField(
                key="attributeName",
                label="Attribute Name",
                type="text",
                placeholder="data-status, class, href...",
                visibleWhen={"key": "checkMode", "in": ["attribute"]},
            ),
            ParamField(
                key="operator",
                label="Operator",
                type="select",
                default="contains",
                options=[{"value": code, "label": label} for code, label in _TEXT_OPS],
                visibleWhen={"key": "checkMode", "in": ["text", "attribute"]},
            ),
            ParamField(
                key="value",
                label="Value",
                type="text",
                placeholder="expected value, or {{item.field}} / {{myVar.field}}",
                supportsTemplate=True,
                visibleWhen=[
                    {"key": "checkMode", "in": ["text", "attribute"]},
                    {"key": "operator", "in": _BINARY_OPS},
                ],
            ),
            ParamField(
                key="resultVar",
                label="Result Variable (optional)",
                type="text",
                placeholder="element_value",
                producesVariable=True,
            ),
        ],
        codegen=codegen_element_if,
    )
)
