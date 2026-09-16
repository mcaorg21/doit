from app.nodes.base import ParamField

SELECTOR_TYPE_OPTIONS = [
    {"value": "css", "label": "CSS Selector"},
    {"value": "id", "label": "ID"},
    {"value": "class_name", "label": "Class Name"},
    {"value": "xpath", "label": "XPath"},
    {"value": "full_xpath", "label": "Full XPath"},
]


def selector_type_field(key: str = "selectorType") -> ParamField:
    return ParamField(key=key, label="Selector Type", type="select", default="css", options=SELECTOR_TYPE_OPTIONS)


def selector_field(key: str = "selector", placeholder: str | None = None) -> ParamField:
    return ParamField(
        key=key,
        label="Selector Value",
        type="text",
        required=True,
        placeholder=placeholder or "e.g. #email, .btn, //button",
    )


def typing_option_fields(clear_key: str = "clearFirst", simulate_key: str = "simulateTyping") -> list[ParamField]:
    """Shared by every node with a free-text input field (Fill Input, Multi Input,
    Login, Microsoft Login, Select Searchable Dropdown) — kept as one shared pair so
    the label text (and its i18n lookup, keyed by exact English text) stays identical
    everywhere it shows up."""
    return [
        ParamField(key=clear_key, label="Clear the field first", type="boolean", default=False),
        ParamField(
            key=simulate_key,
            label="Simulate typing (character by character — needed by some JS-driven inputs)",
            type="boolean",
            default=False,
        ),
    ]


def timeout_field(key: str = "timeout", default_seconds: float = 30) -> ParamField:
    """Shared by every node with a configurable wait-before-acting timeout (Click, Get
    Text, ...) — kept as one helper (with timeout_ms_kwarg below) so the label text and
    the seconds-to-milliseconds conversion stay identical everywhere it shows up."""
    return ParamField(
        key=key,
        label="Timeout (seconds)",
        type="number",
        default=default_seconds,
        placeholder=str(int(default_seconds)),
    )


def timeout_ms_kwarg(params: dict, key: str = "timeout", default_seconds: float = 30) -> str:
    """Converts a timeout_field's value (seconds) into a Playwright `timeout=<ms>`
    keyword-argument source string."""
    try:
        seconds = float(params.get(key) or default_seconds)
    except (TypeError, ValueError):
        seconds = default_seconds
    return f"timeout={int(seconds * 1000)}"


def fill_lines(locator_expr: str, value_expr: str, clear_first: bool, simulate_typing: bool) -> list[str]:
    """Generates the fill statement(s) for one input, honoring the two typing_option_fields
    flags. `press_sequentially` dispatches real keydown/input/keyup events per character —
    some inputs (masks, JS-controlled/React-style fields, autocomplete widgets) ignore
    .fill()'s direct value assignment and need this to actually register."""
    lines = []
    if clear_first:
        lines.append(f"{locator_expr}.clear()")
    if simulate_typing:
        lines.append(f"{locator_expr}.press_sequentially({value_expr})")
    else:
        lines.append(f"{locator_expr}.fill({value_expr})")
    return lines
