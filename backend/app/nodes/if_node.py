from app.codegen.context import CodegenContext, CodegenError
from app.codegen.template_utils import resolve_condition_operand, resolve_variable_operand
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register

# Each type's operator dropdown, and the codegen expression for every (type, operator)
# pair — mirrors n8n's IF node condition builder (Value 1 -> Type -> Operator -> Value 2).
_STRING_OPS = [
    ("exists", "Exists"),
    ("notExists", "Does Not Exist"),
    ("empty", "Is Empty"),
    ("notEmpty", "Is Not Empty"),
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
]
_NUMBER_OPS = [
    ("exists", "Exists"),
    ("notExists", "Does Not Exist"),
    ("empty", "Is Empty"),
    ("notEmpty", "Is Not Empty"),
    ("equal", "Is Equal To"),
    ("notEqual", "Is Not Equal To"),
    ("gt", "Is Greater Than"),
    ("lt", "Is Less Than"),
    ("gte", "Is Greater Than or Equal To"),
    ("lte", "Is Less Than or Equal To"),
]
_DATETIME_OPS = [
    ("exists", "Exists"),
    ("notExists", "Does Not Exist"),
    ("empty", "Is Empty"),
    ("notEmpty", "Is Not Empty"),
    ("equal", "Is Equal To"),
    ("notEqual", "Is Not Equal To"),
    ("isAfter", "Is After"),
    ("isBefore", "Is Before"),
    ("isAfterOrEqual", "Is After or Equal To"),
    ("isBeforeOrEqual", "Is Before or Equal To"),
]
_BOOLEAN_OPS = [
    ("exists", "Exists"),
    ("notExists", "Does Not Exist"),
    ("isTrue", "Is True"),
    ("isFalse", "Is False"),
    ("equal", "Is Equal To"),
    ("notEqual", "Is Not Equal To"),
]
_ARRAY_OPS = [
    ("exists", "Exists"),
    ("notExists", "Does Not Exist"),
    ("empty", "Is Empty"),
    ("notEmpty", "Is Not Empty"),
    ("contains", "Contains"),
    ("notContains", "Does Not Contain"),
    ("lengthEqual", "Length Equal To"),
    ("lengthNotEqual", "Length Not Equal To"),
    ("lengthGt", "Length Greater Than"),
    ("lengthLt", "Length Less Than"),
    ("lengthGte", "Length Greater Than or Equal To"),
    ("lengthLte", "Length Less Than or Equal To"),
]
_OBJECT_OPS = [
    ("exists", "Exists"),
    ("notExists", "Does Not Exist"),
    ("empty", "Is Empty"),
    ("notEmpty", "Is Not Empty"),
]

_OPS_BY_TYPE = {
    "string": _STRING_OPS,
    "number": _NUMBER_OPS,
    "dateTime": _DATETIME_OPS,
    "boolean": _BOOLEAN_OPS,
    "array": _ARRAY_OPS,
    "object": _OBJECT_OPS,
}

# Operators that don't need a second value — everything else does.
_UNARY_OPS = {"exists", "notExists", "empty", "notEmpty", "isTrue", "isFalse"}
_BINARY_OPS = sorted({code for ops in _OPS_BY_TYPE.values() for code, _ in ops} - _UNARY_OPS)

_SHARED_EXPR = {
    "exists": lambda l, r: f"(({l}) is not None)",
    "notExists": lambda l, r: f"(({l}) is None)",
    "empty": lambda l, r: f"_is_empty({l})",
    "notEmpty": lambda l, r: f"(not _is_empty({l}))",
    "equal": lambda l, r: f"(({l}) == ({r}))",
    "notEqual": lambda l, r: f"(({l}) != ({r}))",
}

_TYPE_EXPR_OVERRIDES = {
    "string": {
        "contains": lambda l, r: f"(({r}) in str({l} or ''))",
        "notContains": lambda l, r: f"(({r}) not in str({l} or ''))",
        "startsWith": lambda l, r: f"str({l} or '').startswith({r})",
        "notStartsWith": lambda l, r: f"(not str({l} or '').startswith({r}))",
        "endsWith": lambda l, r: f"str({l} or '').endswith({r})",
        "notEndsWith": lambda l, r: f"(not str({l} or '').endswith({r}))",
        "regex": lambda l, r: f"_regex_match({l}, {r})",
        "notRegex": lambda l, r: f"(not _regex_match({l}, {r}))",
    },
    "number": {
        "gt": lambda l, r: f"_num_compare({l}, {r}, 'gt')",
        "lt": lambda l, r: f"_num_compare({l}, {r}, 'lt')",
        "gte": lambda l, r: f"_num_compare({l}, {r}, 'gte')",
        "lte": lambda l, r: f"_num_compare({l}, {r}, 'lte')",
    },
    "dateTime": {
        "equal": lambda l, r: f"_dt_compare({l}, {r}, 'equal')",
        "notEqual": lambda l, r: f"_dt_compare({l}, {r}, 'not_equal')",
        "isAfter": lambda l, r: f"_dt_compare({l}, {r}, 'after')",
        "isBefore": lambda l, r: f"_dt_compare({l}, {r}, 'before')",
        "isAfterOrEqual": lambda l, r: f"_dt_compare({l}, {r}, 'after_or_equal')",
        "isBeforeOrEqual": lambda l, r: f"_dt_compare({l}, {r}, 'before_or_equal')",
    },
    "boolean": {
        "isTrue": lambda l, r: f"(bool({l}) is True)",
        "isFalse": lambda l, r: f"(bool({l}) is False)",
    },
    "array": {
        "contains": lambda l, r: f"(({r}) in ({l} or []))",
        "notContains": lambda l, r: f"(({r}) not in ({l} or []))",
        "lengthEqual": lambda l, r: f"(len({l} or []) == ({r}))",
        "lengthNotEqual": lambda l, r: f"(len({l} or []) != ({r}))",
        "lengthGt": lambda l, r: f"(len({l} or []) > ({r}))",
        "lengthLt": lambda l, r: f"(len({l} or []) < ({r}))",
        "lengthGte": lambda l, r: f"(len({l} or []) >= ({r}))",
        "lengthLte": lambda l, r: f"(len({l} or []) <= ({r}))",
    },
    "object": {},
}


def _literal_kind(condition_type: str, operator: str) -> str:
    if condition_type == "number":
        return "number"
    if condition_type == "boolean":
        return "boolean"
    if condition_type == "array" and operator.startswith("length"):
        return "number"
    return "string"


def codegen_if(ctx: CodegenContext) -> str:
    condition_type = ctx.params.get("type") or "string"
    operator = ctx.params.get("operator") or "equal"
    ops = _OPS_BY_TYPE.get(condition_type)
    if ops is None or operator not in {code for code, _ in ops}:
        raise CodegenError(
            f"Node '{ctx.node_label}': operator {operator!r} is not valid for type {condition_type!r} — "
            f"re-select the operator after changing the type"
        )

    left = resolve_variable_operand(ctx.params.get("value1"), ctx, "Value 1")
    right = None
    if operator in _BINARY_OPS:
        right = resolve_condition_operand(
            ctx.params.get("value2"), ctx, "Value 2", literal_kind=_literal_kind(condition_type, operator)
        )

    builder = _TYPE_EXPR_OVERRIDES.get(condition_type, {}).get(operator) or _SHARED_EXPR.get(operator)
    if builder is None:
        raise CodegenError(f"Node '{ctx.node_label}': operator {operator!r} is not implemented for type {condition_type!r}")

    return f"if {builder(left, right)}:"


register(
    NodeSpec(
        type="if",
        label="IF",
        category="logic",
        description=(
            "Branches execution based on a condition — pick a type (String/Number/Date & Time/Boolean/"
            "Array/Object), an operator, and the value(s) to compare, n8n-style. Connect its two outputs "
            "to separate true/false paths — in v1 the branches run independently and don't rejoin."
        ),
        example="If {{status}} equals 'Aprovado', branch one way, otherwise the other",
        icon="split",
        opens_block=True,
        is_branch=True,
        params=[
            ParamField(
                key="value1",
                label="Value 1",
                type="text",
                required=True,
                placeholder="{{item.field}} or {{myVar.field}}",
                supportsTemplate=True,
            ),
            ParamField(
                key="type",
                label="Type",
                type="select",
                default="string",
                options=[
                    {"value": "string", "label": "String"},
                    {"value": "number", "label": "Number"},
                    {"value": "dateTime", "label": "Date & Time"},
                    {"value": "boolean", "label": "Boolean"},
                    {"value": "array", "label": "Array"},
                    {"value": "object", "label": "Object"},
                ],
            ),
            ParamField(
                key="operator",
                label="Operator",
                type="select",
                default="equal",
                options=[{"value": code, "label": label} for code, label in _STRING_OPS],
                optionsSource={
                    "key": "type",
                    "map": {t: [{"value": code, "label": label} for code, label in ops] for t, ops in _OPS_BY_TYPE.items()},
                },
            ),
            ParamField(
                key="value2",
                label="Value 2",
                type="text",
                placeholder="value to compare, or {{item.field}}",
                supportsTemplate=True,
                visibleWhen={"key": "operator", "in": _BINARY_OPS},
            ),
        ],
        codegen=codegen_if,
    )
)
