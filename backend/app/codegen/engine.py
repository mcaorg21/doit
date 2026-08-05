from app.codegen.context import CodegenContext, CodegenError
from app.models.workflow import WFEdge, WFNode
from app.nodes.registry import NODE_REGISTRY

HEADER = '''import json
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright


def _dig(obj, path):
    for part in path.split("."):
        if isinstance(obj, list):
            if not part.lstrip("-").isdigit():
                raise ValueError(
                    f"Result Path {path!r}: the response at this point is a list (length {len(obj)}), "
                    f"so {part!r} must be a numeric index, not a key. If the response is already the "
                    f"list you want, leave Result Path empty instead."
                )
            index = int(part)
            if index >= len(obj) or index < -len(obj):
                raise ValueError(f"Result Path {path!r}: index {index} is out of range for a list of length {len(obj)}")
            obj = obj[index]
        elif isinstance(obj, dict):
            if part not in obj:
                raise ValueError(f"Result Path {path!r}: key {part!r} not found — available keys: {list(obj.keys())}")
            obj = obj[part]
        else:
            raise ValueError(f"Result Path {path!r}: can't look up {part!r} on a {type(obj).__name__} value")
    return obj


def _is_empty(value):
    if value is None:
        return True
    if isinstance(value, (str, list, dict, tuple, set)):
        return len(value) == 0
    return False


def _regex_match(value, pattern):
    try:
        return re.search(pattern, str(value if value is not None else "")) is not None
    except re.error:
        return False


def _num_compare(a, b, op):
    try:
        na, nb = float(a), float(b)
    except (TypeError, ValueError):
        return False
    if op == "gt":
        return na > nb
    if op == "lt":
        return na < nb
    if op == "gte":
        return na >= nb
    return na <= nb


def _to_dt(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _dt_compare(a, b, op):
    da, db = _to_dt(a), _to_dt(b)
    if da is None or db is None:
        return False
    if op == "after":
        return da > db
    if op == "before":
        return da < db
    if op == "after_or_equal":
        return da >= db
    if op == "before_or_equal":
        return da <= db
    if op == "equal":
        return da == db
    return da != db
'''


def _node_label(node: WFNode) -> str:
    """The node's title if the user set one, else its id — for user-facing messages."""
    return node.title or node.id


def _indent_fragment(fragment: str, level: int) -> str:
    prefix = "    " * level
    lines = []
    for line in fragment.splitlines():
        lines.append(prefix + line if line.strip() else line)
    return "\n".join(lines)


def _validate_and_index(
    nodes: list[WFNode], edges: list[WFEdge]
) -> tuple[dict[str, WFNode], dict[str, list[WFEdge]], dict[str, int]]:
    node_map = {n.id: n for n in nodes}
    outgoing: dict[str, list[WFEdge]] = {n.id: [] for n in nodes}
    incoming_count: dict[str, int] = {n.id: 0 for n in nodes}

    for e in edges:
        if e.source not in node_map or e.target not in node_map:
            raise CodegenError(f"Edge references unknown node: '{e.source}' -> '{e.target}'")
        outgoing[e.source].append(e)
        incoming_count[e.target] += 1

    for node in nodes:
        spec = NODE_REGISTRY.get(node.type)
        if spec is None:
            raise CodegenError(f"Unknown node type '{node.type}' (node '{_node_label(node)}')")

        out_edges = outgoing[node.id]
        if spec.is_branch:
            handles = [e.sourceHandle for e in out_edges]
            if len(handles) != len(set(handles)):
                raise CodegenError(
                    f"Node '{_node_label(node)}' has more than one connection from the same branch output"
                )
            for h in handles:
                if h not in ("true", "false"):
                    raise CodegenError(
                        f"Node '{_node_label(node)}' is a branching node — outgoing connections must come from its "
                        f"true/false outputs, got {h!r}"
                    )
        elif len(out_edges) > 1:
            raise CodegenError(
                f"Node '{_node_label(node)}' has multiple outgoing connections; "
                f"branching isn't supported for this node type"
            )

    for node_id, count in incoming_count.items():
        if count > 1:
            raise CodegenError(
                f"Node '{_node_label(node_map[node_id])}' has multiple incoming connections; "
                f"merging isn't supported in v1"
            )

    return node_map, outgoing, incoming_count


def generate_script(
    nodes: list[WFNode],
    edges: list[WFEdge],
    preview_node_id: str | None = None,
    preview_var: str | None = None,
) -> str:
    """Single source of truth for the live code preview, the executed script, and the
    variable-preview feature (run the chain up to a node, dump one variable, stop).

    Walks the graph as a tree rooted at the single no-incoming-edge node. Branching
    (the IF node) recurses into its "true"/"false" targets independently — v1 does not
    support the two branches rejoining back into a shared continuation.

    When preview_node_id/preview_var are set, generation stops right after that node's
    own code (skipping the rest of the graph and any closing statements) and appends a
    line that prints the named variable as JSON so the caller can capture its real
    runtime value — the same reason it doesn't require every node to be visited in
    that mode.
    """
    if not nodes:
        return f"{HEADER}\n"

    if preview_node_id is not None and not any(n.id == preview_node_id for n in nodes):
        raise CodegenError(f"Node '{preview_node_id}' not found")

    node_map, outgoing, incoming_count = _validate_and_index(nodes, edges)

    roots = [n for n in nodes if incoming_count[n.id] == 0]
    if len(roots) == 0:
        raise CodegenError("Workflow has no start node — check for a cycle among the connected nodes")
    if len(roots) > 1:
        names = ", ".join(n.id for n in roots)
        raise CodegenError(f"Workflow must have exactly one start node, found {len(roots)}: {names}")

    visited: set[str] = set()
    has_breakpoints = any(n.type == "pause" for n in nodes) or any(e.breakpoint for e in edges)

    def render(
        node_id: str,
        indent: int,
        in_loop: bool,
        browser_var: str | None,
        target_var: str,
        path: frozenset[str],
    ) -> list[str]:
        if node_id in path:
            raise CodegenError(f"Cycle detected at node '{_node_label(node_map[node_id])}'")

        node = node_map[node_id]
        spec = NODE_REGISTRY[node.type]
        visited.add(node_id)
        next_path = path | {node_id}

        ctx = CodegenContext(
            node_id=node.id,
            params=node.params,
            in_loop=in_loop,
            browser_var=browser_var,
            target_var=target_var,
            has_breakpoints=has_breakpoints,
            node_label=_node_label(node),
        )
        fragment = spec.codegen(ctx)
        lines: list[str] = []
        if node.note:
            lines += [_indent_fragment(f"# {n}", indent) for n in node.note.splitlines() if n.strip()]

        # A dedicated marker line (not one of the node's own descriptive prints, which
        # a node's own codegen usually emits only *after* its action finishes) — lets
        # the frontend highlight whichever node is currently running on the canvas,
        # updated the moment each node starts rather than after the fact.
        lines.append(_indent_fragment(f'print("__NODE_START__{node.id}")', indent))

        opens_for_wrap = spec.opens_block(ctx) if callable(spec.opens_block) else spec.opens_block
        # Every node that doesn't open a block (i.e. a single self-contained action, not
        # flow control like a loop/with/if) gets wrapped in try/except so a failure drops
        # straight into pdb at the exact node that broke, instead of crashing the whole
        # run — skipped for Pause (it already calls breakpoint() itself) and entirely for
        # preview-mode generation, whose subprocess has no stdin attached: a breakpoint()
        # there would just hang until the preview's timeout kills it.
        should_wrap = not opens_for_wrap and node.type != "pause" and preview_node_id is None
        if should_wrap:
            error_prefix = repr(f"Tratar erro no node {ctx.node_label}: ")
            try_body = _indent_fragment(fragment, 1)
            wrapped = (
                "try:\n"
                f"{try_body}\n"
                "except Exception as _e:\n"
                f"    print({error_prefix} + str(_e))\n"
                "    breakpoint()"
            )
            lines.append(_indent_fragment(wrapped, indent))
        else:
            lines.append(_indent_fragment(fragment, indent))

        if node_id == preview_node_id:
            # If this node's own fragment ends by opening a block (e.g. a loop or `if`
            # with no body yet — the body normally comes from recursing into downstream
            # nodes, which preview mode skips), pad it with a `pass` so the dump
            # statement right after doesn't land as a syntax error (empty block).
            if fragment.rstrip().endswith(":"):
                lines.append(_indent_fragment("pass", indent + 1))
            dump = f'print("__PREVIEW__" + json.dumps({preview_var}, default=str))\nimport sys; sys.exit(0)'
            lines.append(_indent_fragment(dump, indent))
            return lines

        opens = opens_for_wrap
        body_indent = indent + 1 if opens else indent
        # Only actually enters a loop if this node's block IS a loop (opens) — an
        # HTTP Request with auto-loop turned off, for instance, opens no block at all
        # and shouldn't mark anything downstream as being inside one.
        next_in_loop = in_loop or (opens and spec.category == "dataSource")
        next_browser_var = spec.browser_var_after(ctx) if spec.browser_var_after else browser_var
        next_target_var = spec.target_var_after(ctx) if spec.target_var_after else target_var

        if spec.is_branch:
            by_handle = {e.sourceHandle: e for e in outgoing[node_id]}
            true_edge = by_handle.get("true")
            false_edge = by_handle.get("false")

            if true_edge:
                if true_edge.breakpoint:
                    lines.append(_indent_fragment("breakpoint()", body_indent))
                lines += render(true_edge.target, body_indent, next_in_loop, next_browser_var, next_target_var, next_path)
            else:
                lines.append(_indent_fragment("pass", body_indent))

            if false_edge:
                lines.append(_indent_fragment("else:", indent))
                if false_edge.breakpoint:
                    lines.append(_indent_fragment("breakpoint()", body_indent))
                lines += render(false_edge.target, body_indent, next_in_loop, next_browser_var, next_target_var, next_path)

            return lines

        next_edges = outgoing[node_id]
        if next_edges:
            edge = next_edges[0]
            if edge.breakpoint:
                lines.append(_indent_fragment("breakpoint()", body_indent))
            lines += render(edge.target, body_indent, next_in_loop, next_browser_var, next_target_var, next_path)

        if spec.closing_stmt:
            # Placed after recursing into the rest of this block's chain, so it lands
            # as the last statement *inside* the block (e.g. inside a `with`) rather
            # than after it — the block's own __exit__ would otherwise already have
            # torn things down by the time it ran.
            lines.append(_indent_fragment(spec.closing_stmt(ctx), body_indent))
        elif opens and not next_edges:
            # Nothing to put inside the block this node opened (e.g. a Loop with no
            # downstream nodes) — an empty `for`/`with` body is a SyntaxError, so pad it.
            lines.append(_indent_fragment("pass", body_indent))

        return lines

    body_lines = render(roots[0].id, 0, False, None, "page", frozenset())

    # In preview mode, generation deliberately stops partway through the graph, so
    # nodes past the preview target are expected to stay unvisited.
    if preview_node_id is None and len(visited) != len(nodes):
        missing = ", ".join(n.id for n in nodes if n.id not in visited)
        raise CodegenError(f"Workflow has disconnected node(s): {missing}")

    body = "\n".join(body_lines)
    return f"{HEADER}\n{body}\n"
