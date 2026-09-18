"""Turns an arbitrary Python automation script into this app's own workflow graph
format via an LLM — prompt construction, response parsing, and a layered repair
pass that tries hard to turn "the AI got something wrong" into a usable (if
imperfect) result rather than a hard failure. See the plan file for the full design
rationale.
"""

import json
import re
import textwrap

from fastapi import HTTPException

from app.codegen.context import CodegenError
from app.codegen.engine import generate_script
from app.models.llm_import import ReconstructPythonResponse
from app.models.workflow import Position, WFEdge, WFNode
from app.nodes.registry import NODE_REGISTRY
from app.services.llm_providers import LLMError, call_llm
from app.storage import credential_store
from app.storage.ids import gen_id

CREDENTIAL_TYPE_TO_PROVIDER = {"openai": "openai", "anthropic": "anthropic"}

LAYOUT_STEP_X = 180
LAYOUT_Y = 200

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


class ReconstructionError(Exception):
    """Unrecoverable — surfaced to the caller as a 422 with a clear, user-facing message."""


RECONSTRUCTION_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "params": {"type": "object"},
                    "note": {"type": ["string", "null"]},
                },
                "required": ["id", "type", "params"],
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "sourceHandle": {"type": ["string", "null"]},
                },
                "required": ["id", "source", "target"],
            },
        },
    },
    "required": ["name", "nodes", "edges"],
}

_EXAMPLE_OUTPUT = {
    "name": "Login and scrape leads",
    "nodes": [
        {"id": "n1", "type": "open_browser", "params": {"headless": False}, "note": None},
        {"id": "n2", "type": "goto", "params": {"url": "https://example.com/login"}, "note": None},
        {
            "id": "n3",
            "type": "unknown",
            "params": {
                "code": "page.fill('#totp', pyotp.TOTP(SECRET).now())",
                "sourceHint": "TOTP code generation has no matching node type",
            },
            "note": None,
        },
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"},
    ],
}


def reconstruct_workflow(project_id: str, python_code: str, credential_id: str) -> ReconstructPythonResponse:
    if not python_code.strip():
        raise ReconstructionError("The uploaded file is empty")

    try:
        credential = credential_store.get_credential(project_id, credential_id)
    except HTTPException as exc:
        raise ReconstructionError(str(exc.detail)) from exc

    # Case-insensitive: the credential's Type is free text typed by the user, so
    # "OpenAI"/"openai "/etc. should all still resolve to the right provider.
    provider = CREDENTIAL_TYPE_TO_PROVIDER.get(credential.type.strip().lower())
    if provider is None:
        raise ReconstructionError(
            f"Credential '{credential.name}' has type {credential.type!r} — expected "
            f"'openai' or 'anthropic' to use it for AI import"
        )

    catalog = build_node_catalog()
    try:
        raw_text = call_llm(
            provider,
            credential.value,
            _build_system_prompt(catalog),
            _build_user_prompt(python_code),
            RECONSTRUCTION_SCHEMA,
        )
    except LLMError as exc:
        raise ReconstructionError(f"AI request failed: {exc}") from exc

    data = _parse_json_response(raw_text)
    nodes, edges, warnings = build_and_validate_graph(data, catalog)

    if not nodes:
        raise ReconstructionError("The AI didn't produce any nodes for this script")

    # Reuses the engine's own structural validation (single root, <=1 incoming edge
    # per node, IF branch handle rules, cycles) instead of reimplementing it — catches
    # anything the repair steps above didn't preempt, as a clear CodegenError-derived
    # message rather than a broken saved workflow.
    try:
        generate_script(nodes, edges, project_id)
    except CodegenError as exc:
        raise ReconstructionError(f"AI produced an unrunnable workflow: {exc}") from exc

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        name = "Imported workflow"

    return ReconstructPythonResponse(
        name=name.strip(),
        nodes=nodes,
        edges=edges,
        warnings=warnings,
        unknownCount=sum(1 for n in nodes if n.type == "unknown"),
    )


def build_node_catalog() -> list[dict]:
    # Exactly what GET /api/node-types serves — the LLM's vocabulary of what it's
    # allowed to emit, read straight from the registry (not over HTTP).
    return [spec.to_public_dict() for spec in NODE_REGISTRY.values()]


def _structural_rules() -> str:
    # Computed fresh per call (not frozen at import time) so a newly-registered
    # branching node type (e.g. element_if, added alongside "if") shows up here
    # automatically instead of leaving this text silently stale/wrong — see
    # NodeSpec.is_branch (app/nodes/base.py) for what qualifies.
    branch_types = sorted(t for t, spec in NODE_REGISTRY.items() if spec.is_branch)
    branch_list = ", ".join(f'"{t}"' for t in branch_types) or "none currently registered"
    return (
        "Structural rules (violating these makes the workflow unusable):\n"
        "- Exactly one root node (a node with no incoming edge) — every other node "
        "must be reachable from it.\n"
        "- At most one incoming edge per node — branches never merge back together.\n"
        f"- Only a branching node (currently: {branch_list} — the authoritative check "
        "is `isBranch: true` on that type's entry in get_node_catalog()'s node types) "
        "may have two outgoing edges, and they must set `sourceHandle` to exactly "
        "\"true\" and \"false\" respectively. Every other node has at most one "
        "outgoing edge.\n"
        "- No cycles.\n"
        "- Use the real node types that open a block for anything that actually opens "
        "a nested scope in the source — `open_browser` for launching the browser, "
        "`loop` for iterating a list, `if` for a conditional, `http_request` (with "
        "autoLoop) for looping over an API result — their nested body becomes the "
        "downstream node chain via edges, never inlined as one big snippet.\n"
        "- Reserve \"unknown\" strictly for self-contained, straight-line code with "
        "no loop/if/with of its own — the builder has no way to know an `unknown` "
        "fragment needs children nested inside it.\n"
        "- For an `unknown` node, put the ORIGINAL source lines verbatim in "
        "`params.code`, and a short phrase in `params.sourceHint` explaining why it "
        "didn't map to anything.\n"
        "- For any field whose schema entry has a non-null `credentialType` (e.g. an "
        "API-key picker), leave it empty/null and add a `note` telling the user to "
        "pick a credential — you cannot know which project credential to reference.\n"
        "- Only emit `params` keys that exist in that node type's schema above.\n"
        "- Do not include a `position` field at all — it's computed separately.\n"
    )


def _build_system_prompt(catalog: list[dict]) -> str:
    return (
        "You convert an arbitrary Python browser-automation script (Playwright- or "
        "Selenium-style, not necessarily written for this tool) into a JSON workflow "
        "graph for a specific node-based automation builder.\n\n"
        "Available node types (use ONLY these `type` values, plus \"unknown\" for "
        "anything that doesn't fit — see rules below). Each entry's `params` "
        "describes the exact keys you may set for that node type:\n\n"
        f"{json.dumps(catalog, indent=2)}\n\n"
        f"{_structural_rules()}\n"
        "Output format — respond with ONLY a JSON object shaped exactly like this "
        "example (no prose, no markdown fences):\n\n"
        f"{json.dumps(_EXAMPLE_OUTPUT, indent=2)}"
    )


def _build_user_prompt(python_code: str) -> str:
    return (
        "Convert the following Python automation script into the workflow graph "
        f"JSON described above.\n\n```python\n{python_code}\n```"
    )


def _parse_json_response(raw_text: str) -> dict:
    text = raw_text.strip()
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReconstructionError(
            f"Could not parse the AI's response as JSON ({exc}). Response (tail): {raw_text[-500:]}"
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list) or not isinstance(data.get("edges"), list):
        raise ReconstructionError("The AI's response wasn't shaped like a workflow (missing/invalid nodes or edges)")
    return data


def _stringify_unmapped(attempted_type: str, params: dict) -> str:
    return "\n".join(
        [
            f"# AI attempted node type '{attempted_type}', which doesn't exist — needs manual implementation.",
            f"# Attempted params: {params!r}",
            "pass",
        ]
    )


def build_and_validate_graph(data: dict, catalog: list[dict]) -> tuple[list[WFNode], list[WFEdge], list[str]]:
    schema_by_type = {spec["type"]: spec for spec in catalog}
    warnings: list[str] = []

    id_map: dict[str, str] = {}
    nodes: list[WFNode] = []
    for i, raw in enumerate(data.get("nodes") or []):
        if not isinstance(raw, dict) or not raw.get("id"):
            warnings.append(f"Skipped a malformed node at position {i}")
            continue
        old_id = str(raw["id"])
        new_id = gen_id("node")
        id_map[old_id] = new_id

        node_type = str(raw.get("type") or "unknown")
        params = raw.get("params") if isinstance(raw.get("params"), dict) else {}

        spec = schema_by_type.get(node_type)
        if node_type != "unknown" and spec is None:
            warnings.append(f"Node '{old_id}': unknown type '{node_type}' from the AI — downgraded to a placeholder")
            params = {"code": _stringify_unmapped(node_type, params), "sourceHint": f"AI attempted type '{node_type}'"}
            node_type = "unknown"
        elif spec is not None:
            allowed_keys = {p["key"] for p in spec["params"]}
            dropped = sorted(set(params) - allowed_keys)
            if dropped:
                warnings.append(f"Node '{old_id}': dropped unrecognized param(s) {dropped}")
            params = {k: v for k, v in params.items() if k in allowed_keys}

        if node_type == "unknown":
            params["code"] = textwrap.dedent(str(params.get("code") or "pass")).strip("\n") or "pass"

        note = raw.get("note") if isinstance(raw.get("note"), str) else None
        nodes.append(WFNode(id=new_id, type=node_type, position=Position(x=0, y=0), params=params, note=note))

    valid_ids = {n.id for n in nodes}
    edges: list[WFEdge] = []
    for i, raw in enumerate(data.get("edges") or []):
        if not isinstance(raw, dict):
            warnings.append(f"Skipped a malformed edge at position {i}")
            continue
        source = id_map.get(str(raw.get("source")))
        target = id_map.get(str(raw.get("target")))
        if source not in valid_ids or target not in valid_ids:
            warnings.append(f"Dropped an edge referencing a missing node ({raw.get('source')} -> {raw.get('target')})")
            continue
        source_handle = raw.get("sourceHandle") if raw.get("sourceHandle") in ("true", "false") else None
        edges.append(WFEdge(id=gen_id("edge"), source=source, target=target, sourceHandle=source_handle))

    _chain_disconnected_segments(nodes, edges, warnings)
    _apply_layout(nodes)

    return nodes, edges, warnings


def _chain_disconnected_segments(nodes: list[WFNode], edges: list[WFEdge], warnings: list[str]) -> None:
    if not nodes:
        return
    targets = {e.target for e in edges}
    roots = [n.id for n in nodes if n.id not in targets]
    if len(roots) <= 1:
        return

    outgoing: dict[str, list[str]] = {n.id: [] for n in nodes}
    for e in edges:
        outgoing[e.source].append(e.target)

    def segment_tail(root_id: str) -> str:
        # Simple single-path walk (take the first outgoing edge each step) — good
        # enough for the "AI split one linear script into a few pieces" case this
        # exists for; a segment ending in an actual branch is a rarer edge case for a
        # reconstruction-from-linear-script scenario.
        current = root_id
        seen = {current}
        while outgoing[current]:
            nxt = outgoing[current][0]
            if nxt in seen:
                break
            current = nxt
            seen.add(current)
        return current

    for i in range(len(roots) - 1):
        tail = segment_tail(roots[i])
        edges.append(WFEdge(id=gen_id("edge"), source=tail, target=roots[i + 1]))
        outgoing[tail].append(roots[i + 1])

    warnings.append(
        f"The AI produced {len(roots)} disconnected segments — chained them into a single sequence; verify the order is correct"
    )


def _apply_layout(nodes: list[WFNode]) -> None:
    # Ignores whatever (if anything) the AI said about position — never trusted to
    # produce sane pixel coordinates. Mirrors the canvas's existing horizontal flow.
    for i, node in enumerate(nodes):
        node.position = Position(x=LAYOUT_STEP_X * i, y=LAYOUT_Y)


def downgrade_node_if_missing_credential(node: WFNode, catalog: list[dict], project_id: str | None = None) -> str | None:
    """MCP-only safety net (not used by reconstruct_workflow): a credentialType-tagged
    param (e.g. microsoft_login's credentialId) left empty, or pointing at an id that
    doesn't actually exist in this project, can never resolve — generate_script's
    resolve_credential_value would raise CodegenError on it (required=True on every
    credentialId field; see app/codegen/template_utils.py:40-57). An MCP client can
    look up a real id via the list_credentials tool first, so this only downgrades
    when that wasn't done (or the id it supplied doesn't check out) — a node whose
    credential field(s) already hold a real, existing credential id passes through
    unchanged. Downgrades to the same "unknown" placeholder mechanism used for
    unmapped types when a downgrade IS needed. Mutates `node` in place. Returns a
    warning string, or None if the node didn't need a credential (or already has a
    valid one)."""
    spec = {s["type"]: s for s in catalog}.get(node.type)
    if spec is None:
        return None
    cred_fields = [p for p in spec["params"] if p.get("credentialType")]
    if not cred_fields:
        return None

    missing_field = None
    for field in cred_fields:
        value = (node.params.get(field["key"]) or "").strip()
        if not value:
            missing_field = field
            break
        if project_id is not None:
            from fastapi import HTTPException

            from app.storage import credential_store

            try:
                credential_store.get_credential(project_id, value)
            except HTTPException:
                missing_field = field
                break
    if missing_field is None:
        return None

    original_type, original_params = node.type, dict(node.params)
    node.type = "unknown"
    node.params = {
        "code": _stringify_unmapped(original_type, original_params),
        "sourceHint": (
            f"Needs a '{missing_field['credentialType']}' credential — pick one in the "
            f"editor, then replace this placeholder with a real '{original_type}' node"
        ),
    }
    return f"Needs a credential — downgraded from '{original_type}' to a placeholder"
