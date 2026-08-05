import json
import keyword
import re
from typing import Any

from app.codegen.context import CodegenContext, CodegenError

_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}")
_FULL_TEMPLATE_RE = re.compile(r"^\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}$")
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def validate_identifier(name: str | None, ctx: CodegenContext, field_label: str) -> str:
    """Validates a user-typed value that will be spliced into generated code as a bare
    Python identifier (e.g. a variable name) — rejects anything that isn't a safe,
    unambiguous name rather than trying to sanitize it, since silent rewriting could
    collide with another variable or hide a typo from the user."""
    if not name:
        raise CodegenError(f"Node '{ctx.node_label}': '{field_label}' is required")
    if not _IDENTIFIER_RE.match(name) or keyword.iskeyword(name):
        raise CodegenError(
            f"Node '{ctx.node_label}': '{field_label}' must be a valid variable name "
            f"(letters, numbers, underscore, not starting with a digit, not a Python keyword) — got {name!r}"
        )
    return name


def validate_safe_name(name: str, ctx: CodegenContext, field_label: str) -> str:
    """Validates a user-typed value used as a filesystem path segment (e.g. a browser
    profile directory name) — restricts to a safe charset to prevent path traversal."""
    if not name or not _SAFE_NAME_RE.match(name):
        raise CodegenError(
            f"Node '{ctx.node_label}': '{field_label}' may only contain letters, numbers, "
            f"underscore and hyphen — got {name!r}"
        )
    return name


def validate_json_array(raw: str, ctx: CodegenContext, field_label: str) -> str:
    """Validates a user-typed value that will be parsed as a JSON array at runtime —
    catches malformed JSON and non-array values at codegen time with a clear message
    instead of letting the generated script fail with a raw JSONDecodeError."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CodegenError(f"Node '{ctx.node_label}': '{field_label}' is not valid JSON — {exc}") from exc
    if not isinstance(parsed, list):
        raise CodegenError(
            f"Node '{ctx.node_label}': '{field_label}' must be a JSON array (e.g. [1, 2, 3]), "
            f"got a {type(parsed).__name__}"
        )
    return raw


_SELECTOR_PREFIXES = {"id": "#", "class_name": ".", "xpath": "xpath=", "full_xpath": "xpath="}


def build_selector_literal(raw: str, selector_type: str) -> str:
    """Builds a Playwright-ready selector literal from a raw value + a Selenium-style
    locator strategy (css / id / class_name / xpath) — the piece resolve_selector()
    delegates to, factored out so nodes with more than one selector per instance (e.g.
    Multi Input's per-row selector) can use the same logic without a ctx.params key."""
    prefix = _SELECTOR_PREFIXES.get(selector_type, "")
    return repr(prefix + raw)


def resolve_selector(ctx: CodegenContext, selector_key: str = "selector", type_key: str = "selectorType") -> str:
    """Builds a Playwright-ready selector literal from ctx.params, computed at codegen
    time since the strategy is a fixed structural choice, not a per-item runtime value."""
    raw = ctx.params.get(selector_key) or ""
    selector_type = ctx.params.get(type_key, "css")
    return build_selector_literal(raw, selector_type)


def _validate_path_base(path: str, ctx: CodegenContext) -> list[str]:
    parts = path.split(".")
    if parts[0] == "item" and not ctx.in_loop:
        raise CodegenError(
            f"Node '{ctx.node_label}': template reference '{{{{{path}}}}}' uses 'item', but this node isn't "
            f"inside a loop (a Loop node, or an HTTP Request with 'Loop automatically' on) — did you mean "
            f"to reference a variable set by an earlier node instead (e.g. '{{{{myVar.{'.'.join(parts[1:]) or 'field'}}}}}')?"
        )
    return parts


def _path_to_subscript(path: str, ctx: CodegenContext) -> str:
    parts = _validate_path_base(path, ctx)
    expr = parts[0]
    for part in parts[1:]:
        expr += f"[{part!r}]"
    return expr


def _path_to_safe_get(path: str, ctx: CodegenContext) -> str:
    """Like _path_to_subscript, but nested lookups use .get() with a None fallback
    instead of raising KeyError on a missing key — used for the IF node's operands,
    where a missing field should make "exists"/"is empty" evaluate cleanly instead of
    crashing the whole run."""
    parts = _validate_path_base(path, ctx)
    expr = parts[0]
    for part in parts[1:]:
        expr = f"({expr} or {{}}).get({part!r})"
    return expr


def resolve_variable_operand(raw: str | None, ctx: CodegenContext, field_label: str) -> str:
    """Resolves a field that must reference a variable (via '{{path.to.value}}') —
    used by the IF node's left-hand operand, which only makes sense as a reference,
    never a literal. Nested lookups are missing-key-safe (see _path_to_safe_get)."""
    text = (raw or "").strip()
    if not text:
        raise CodegenError(f"Node '{ctx.node_label}': '{field_label}' is required")
    m = _FULL_TEMPLATE_RE.match(text)
    if not m:
        raise CodegenError(
            f"Node '{ctx.node_label}': '{field_label}' must reference a variable using {{{{...}}}} "
            f"(e.g. {{{{item.field}}}} or {{{{myVar.field}}}}) — got {text!r}"
        )
    return _path_to_safe_get(m.group(1), ctx)


def resolve_condition_operand(raw: str | None, ctx: CodegenContext, field_label: str, literal_kind: str = "string") -> str:
    """Resolves the IF node's right-hand operand: '{{path.to.value}}' (the whole
    field, no surrounding text) becomes a variable reference; anything else is a
    literal, coerced per `literal_kind` ("string" | "number" | "boolean")."""
    text = (raw or "").strip()
    m = _FULL_TEMPLATE_RE.match(text)
    if m:
        return _path_to_safe_get(m.group(1), ctx)
    if literal_kind == "number":
        if text == "":
            raise CodegenError(f"Node '{ctx.node_label}': '{field_label}' must be a number or a {{{{variable}}}} reference")
        try:
            num = float(text)
        except ValueError:
            raise CodegenError(
                f"Node '{ctx.node_label}': '{field_label}' must be a number or a {{{{variable}}}} reference — got {text!r}"
            ) from None
        return repr(int(num) if num.is_integer() else num)
    if literal_kind == "boolean":
        low = text.lower()
        if low in ("true", "1", "yes"):
            return "True"
        if low in ("false", "0", "no", ""):
            return "False"
        raise CodegenError(
            f"Node '{ctx.node_label}': '{field_label}' must be true/false or a {{{{variable}}}} reference — got {text!r}"
        )
    return repr(text)


def _escape_fstring_literal(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("{", "{{").replace("}", "}}")


def render_template_expr(raw_value: Any, ctx: CodegenContext) -> str:
    """Turns a raw param value into a Python expression source string.

    Plain strings become literals (`repr(...)`); strings containing `{{item.field}}`
    become an f-string referencing the current loop variable.
    """
    if not isinstance(raw_value, str):
        return repr(raw_value)

    matches = list(_TEMPLATE_RE.finditer(raw_value))
    if not matches:
        return repr(raw_value)

    body: list[str] = []
    last_end = 0
    for m in matches:
        body.append(_escape_fstring_literal(raw_value[last_end : m.start()]))
        body.append("{" + _path_to_subscript(m.group(1), ctx) + "}")
        last_end = m.end()
    body.append(_escape_fstring_literal(raw_value[last_end:]))

    return 'f"' + "".join(body) + '"'
