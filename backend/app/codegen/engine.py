from app.codegen.context import CodegenContext, CodegenError
from app.models.workflow import WFEdge, WFNode
from app.nodes.registry import NODE_REGISTRY

HEADER = '''import json
import requests
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
'''


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
            raise CodegenError(f"Unknown node type '{node.type}' (node '{node.id}')")

        out_edges = outgoing[node.id]
        if spec.is_branch:
            handles = [e.sourceHandle for e in out_edges]
            if len(handles) != len(set(handles)):
                raise CodegenError(f"Node '{node.id}' has more than one connection from the same branch output")
            for h in handles:
                if h not in ("true", "false"):
                    raise CodegenError(
                        f"Node '{node.id}' is a branching node — outgoing connections must come from its "
                        f"true/false outputs, got {h!r}"
                    )
        elif len(out_edges) > 1:
            raise CodegenError(
                f"Node '{node.id}' has multiple outgoing connections; branching isn't supported for this node type"
            )

    for node_id, count in incoming_count.items():
        if count > 1:
            raise CodegenError(f"Node '{node_id}' has multiple incoming connections; merging isn't supported in v1")

    return node_map, outgoing, incoming_count


def generate_script(nodes: list[WFNode], edges: list[WFEdge]) -> str:
    """Single source of truth for both the live preview and the executed script.

    Walks the graph as a tree rooted at the single no-incoming-edge node. Branching
    (the IF node) recurses into its "true"/"false" targets independently — v1 does not
    support the two branches rejoining back into a shared continuation.
    """
    if not nodes:
        return f"{HEADER}\n"

    node_map, outgoing, incoming_count = _validate_and_index(nodes, edges)

    roots = [n for n in nodes if incoming_count[n.id] == 0]
    if len(roots) == 0:
        raise CodegenError("Workflow has no start node — check for a cycle among the connected nodes")
    if len(roots) > 1:
        names = ", ".join(n.id for n in roots)
        raise CodegenError(f"Workflow must have exactly one start node, found {len(roots)}: {names}")

    visited: set[str] = set()

    def render(node_id: str, indent: int, in_loop: bool, browser_var: str | None, path: frozenset[str]) -> list[str]:
        if node_id in path:
            raise CodegenError(f"Cycle detected at node '{node_id}'")

        node = node_map[node_id]
        spec = NODE_REGISTRY[node.type]
        visited.add(node_id)
        next_path = path | {node_id}

        ctx = CodegenContext(node_id=node.id, params=node.params, in_loop=in_loop, browser_var=browser_var)
        fragment = spec.codegen(ctx)
        lines: list[str] = []
        if node.note:
            lines += [_indent_fragment(f"# {n}", indent) for n in node.note.splitlines() if n.strip()]
        lines.append(_indent_fragment(fragment, indent))

        body_indent = indent + 1 if spec.opens_block else indent
        next_in_loop = in_loop or spec.category == "dataSource"
        next_browser_var = spec.browser_var_after(ctx) if spec.browser_var_after else browser_var

        if spec.is_branch:
            by_handle = {e.sourceHandle: e for e in outgoing[node_id]}
            true_edge = by_handle.get("true")
            false_edge = by_handle.get("false")

            if true_edge:
                if true_edge.breakpoint:
                    lines.append(_indent_fragment("breakpoint()", body_indent))
                lines += render(true_edge.target, body_indent, next_in_loop, next_browser_var, next_path)
            else:
                lines.append(_indent_fragment("pass", body_indent))

            if false_edge:
                lines.append(_indent_fragment("else:", indent))
                if false_edge.breakpoint:
                    lines.append(_indent_fragment("breakpoint()", body_indent))
                lines += render(false_edge.target, body_indent, next_in_loop, next_browser_var, next_path)

            return lines

        next_edges = outgoing[node_id]
        if next_edges:
            edge = next_edges[0]
            if edge.breakpoint:
                lines.append(_indent_fragment("breakpoint()", body_indent))
            lines += render(edge.target, body_indent, next_in_loop, next_browser_var, next_path)

        if spec.closing_stmt:
            # Placed after recursing into the rest of this block's chain, so it lands
            # as the last statement *inside* the block (e.g. inside a `with`) rather
            # than after it — the block's own __exit__ would otherwise already have
            # torn things down by the time it ran.
            lines.append(_indent_fragment(spec.closing_stmt(ctx), body_indent))

        return lines

    body_lines = render(roots[0].id, 0, False, None, frozenset())

    if len(visited) != len(nodes):
        missing = ", ".join(n.id for n in nodes if n.id not in visited)
        raise CodegenError(f"Workflow has disconnected node(s): {missing}")

    body = "\n".join(body_lines)
    return f"{HEADER}\n{body}\n"
