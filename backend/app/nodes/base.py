from dataclasses import dataclass
from typing import Any, Callable, Literal

FieldType = Literal[
    "text", "textarea", "number", "select", "boolean", "fieldList", "clickList", "keyValueList", "fileList", "textList"
]
NodeCategory = Literal["trigger", "dataSource", "browser", "action", "logic", "function"]


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
    producesVariable: bool = False
    """True when this field's value names a Python variable that this node assigns
    (e.g. Element Present?'s "resultVar") — lets the frontend offer it as a pickable
    source for other nodes that consume a named variable (e.g. Loop's "Variable from
    earlier node" mode)."""
    consumesVariable: bool = False
    """True when this field should be filled in by picking from an upstream node's
    producesVariable field (e.g. Loop's "arrayVar") rather than typed freely — the
    frontend renders a picker with a live preview instead of a plain text input."""
    visibleWhen: dict[str, Any] | list[dict[str, Any]] | None = None
    """{"key": <sibling param key>, "equals": <value>} or {"key": ..., "in": [<values>]} —
    the frontend only shows this field when the sibling param currently equals that
    value / is one of those values (e.g. Result Variable only makes sense when "Loop
    automatically" is off; the IF node's "Value 2" only makes sense for operators that
    take a second operand). Can also be a LIST of such conditions, all of which must
    hold (AND) — e.g. HTTP Request's JSON-mode Result Variable needs both "autoLoop is
    off" AND "responseType is json", since a single condition can't express that and
    the two toggles are otherwise independent."""
    optionsSource: dict[str, Any] | None = None
    """{"key": <sibling param key>, "map": {<sibling value>: [{"value":.., "label":..}, ...]}} —
    when set, this field's dropdown options are looked up from `map` using the
    sibling field's current value instead of the static `options` list (e.g. the IF
    node's "Operator" choices depend on its "Type" field)."""
    autoGenerate: bool = False
    """True when this field should be seeded with a fresh random token client-side
    the moment the node is added (rather than a fixed `default`), and shown read-only
    with a "regenerate" button (e.g. Webhook's Secret) — every node instance gets its
    own value instead of a shared spec-level default."""
    credentialType: str | None = None
    """When set, this field stores a credential id and the frontend renders it as a
    dropdown populated from the project's Credentials (see app/models/credential.py),
    filtered to this type (e.g. "2captcha") — the node's own codegen resolves the id
    to the credential's actual secret value via ctx.project_id at generation time."""


@dataclass
class NodeSpec:
    type: str
    label: str
    category: NodeCategory
    description: str
    params: list[ParamField]
    codegen: Callable[[Any], str]
    icon: str | None = None
    example: str | None = None
    """One concrete, concise sentence showing this node doing something real (e.g.
    "Fills '#email' with 'john@example.com'") — shown alongside `description` in the
    palette's hover tooltip so someone browsing node types can tell what a node
    actually DOES without adding it first."""
    opens_block: bool | Callable[[Any], bool] = False
    """Whether this node's fragment ends by opening an indented block (a `for`/`with`
    line). Can be a per-instance callable when that depends on the node's own params
    (e.g. HTTP Request only opens its loop when "loop automatically" is on)."""
    closing_stmt: Callable[[Any], str] | None = None
    is_branch: bool = False
    """True for nodes with two named outgoing edges (sourceHandle "true"/"false"),
    e.g. the IF node. Branches don't rejoin in v1 — each is an independent tail."""
    browser_var_after: Callable[[Any], str | None] | None = None
    """If set, replaces CodegenContext.browser_var for downstream nodes with this
    function's return value (e.g. Open Browser sets it to "browser"/"context", Close
    Browser resets it to None). Nodes that don't touch browser state leave this unset
    so the incoming value just passes through unchanged."""
    target_var_after: Callable[[Any], str] | None = None
    """If set, replaces CodegenContext.target_var for downstream nodes (e.g. Switch
    Frame sets it to "frame", Open Browser resets it to "page")."""
    demo_codegen: Callable[[Any], str] | None = None
    """Optional alternate codegen used ONLY by the MCP live-demo path
    (app/mcp/live_sessions.py::run_demo_step), for a node whose normal `codegen`
    fragment needs an indented block (e.g. Download File's `with page.expect_download
    ...`) that can't be sent to a paused pdb prompt one line at a time. When set, its
    output MUST be flat (no line may start with whitespace) — live-demo trusts it
    without re-checking. When unset, run_demo_step falls back to the normal `codegen`
    output and rejects the node for live demo if THAT turns out to be indented,
    rather than risk sending broken code to the live session."""

    def to_public_dict(self) -> dict:
        """Serializable form for the frontend — excludes the server-only codegen callables."""
        return {
            "type": self.type,
            "label": self.label,
            "category": self.category,
            "description": self.description,
            "example": self.example,
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
                    "producesVariable": p.producesVariable,
                    "consumesVariable": p.consumesVariable,
                    "visibleWhen": p.visibleWhen,
                    "optionsSource": p.optionsSource,
                    "autoGenerate": p.autoGenerate,
                    "credentialType": p.credentialType,
                }
                for p in self.params
            ],
        }
