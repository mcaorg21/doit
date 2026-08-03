from dataclasses import dataclass
from typing import Any, Callable, Literal

FieldType = Literal["text", "textarea", "number", "select", "boolean"]
NodeCategory = Literal["dataSource", "browser", "action", "logic"]


@dataclass
class ParamField:
    key: str
    label: str
    type: FieldType
    required: bool = False
    default: Any = None
    options: list[dict] | None = None  # for "select": [{"value": "GET", "label": "GET"}, ...]
    placeholder: str | None = None
    supportsTemplate: bool = False


@dataclass
class NodeSpec:
    type: str
    label: str
    category: NodeCategory
    description: str
    params: list[ParamField]
    codegen: Callable[[Any], str]
    icon: str | None = None
    opens_block: bool = False
    closing_stmt: Callable[[Any], str] | None = None
    is_branch: bool = False
    """True for nodes with two named outgoing edges (sourceHandle "true"/"false"),
    e.g. the IF node. Branches don't rejoin in v1 — each is an independent tail."""
    browser_var_after: Callable[[Any], str | None] | None = None
    """If set, replaces CodegenContext.browser_var for downstream nodes with this
    function's return value (e.g. Open Browser sets it to "browser"/"context", Close
    Browser resets it to None). Nodes that don't touch browser state leave this unset
    so the incoming value just passes through unchanged."""

    def to_public_dict(self) -> dict:
        """Serializable form for the frontend — excludes the server-only codegen callables."""
        return {
            "type": self.type,
            "label": self.label,
            "category": self.category,
            "description": self.description,
            "icon": self.icon,
            "isBranch": self.is_branch,
            "params": [
                {
                    "key": p.key,
                    "label": p.label,
                    "type": p.type,
                    "required": p.required,
                    "default": p.default,
                    "options": p.options,
                    "placeholder": p.placeholder,
                    "supportsTemplate": p.supportsTemplate,
                }
                for p in self.params
            ],
        }
