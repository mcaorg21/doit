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
