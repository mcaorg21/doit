import keyword
import re
from typing import Any

from app.codegen.context import CodegenContext, CodegenError

_TEMPLATE_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}")
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def validate_identifier(name: str, ctx: CodegenContext, field_label: str) -> str:
    """Validates a user-typed value that will be spliced into generated code as a bare
    Python identifier (e.g. a variable name) — rejects anything that isn't a safe,
    unambiguous name rather than trying to sanitize it, since silent rewriting could
    collide with another variable or hide a typo from the user."""
    if not name or not _IDENTIFIER_RE.match(name) or keyword.iskeyword(name):
        raise CodegenError(
            f"Node '{ctx.node_id}': '{field_label}' must be a valid variable name "
            f"(letters, numbers, underscore, not starting with a digit, not a Python keyword) — got {name!r}"
        )
    return name


def validate_safe_name(name: str, ctx: CodegenContext, field_label: str) -> str:
    """Validates a user-typed value used as a filesystem path segment (e.g. a browser
    profile directory name) — restricts to a safe charset to prevent path traversal."""
    if not name or not _SAFE_NAME_RE.match(name):
        raise CodegenError(
            f"Node '{ctx.node_id}': '{field_label}' may only contain letters, numbers, "
            f"underscore and hyphen — got {name!r}"
        )
    return name


_SELECTOR_PREFIXES = {"id": "#", "class_name": ".", "xpath": "xpath=", "full_xpath": "xpath="}


def resolve_selector(ctx: CodegenContext, selector_key: str = "selector", type_key: str = "selectorType") -> str:
    """Builds a Playwright-ready selector literal from a raw value + a Selenium-style
    locator strategy (css / id / class_name / xpath), computed at codegen time since
    the strategy is a fixed structural choice, not a per-item runtime value."""
    raw = ctx.params.get(selector_key) or ""
    selector_type = ctx.params.get(type_key, "css")
    prefix = _SELECTOR_PREFIXES.get(selector_type, "")
    return repr(prefix + raw)


def _path_to_subscript(path: str) -> str:
    parts = path.split(".")
    if parts[0] != "item":
        raise CodegenError(
            f"Unsupported template reference '{{{{{path}}}}}' — only 'item.<field>' is supported in v1"
        )
    expr = "item"
    for part in parts[1:]:
        expr += f"[{part!r}]"
    return expr


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

    if not ctx.in_loop:
        raise CodegenError(
            f"Node '{ctx.node_id}' uses a template expression ({{{{...}}}}) but is not inside a data-source loop"
        )

    body: list[str] = []
    last_end = 0
    for m in matches:
        body.append(_escape_fstring_literal(raw_value[last_end : m.start()]))
        body.append("{" + _path_to_subscript(m.group(1)) + "}")
        last_end = m.end()
    body.append(_escape_fstring_literal(raw_value[last_end:]))

    return 'f"' + "".join(body) + '"'
