from app.models.workflow import WFEdge, WFNode, Workflow

# Node types allowed to be a workflow's start node when it's published — anything
# else can only ever be run manually (the Run button), never by the scheduler or a
# webhook call.
TRIGGER_NODE_TYPES = {"schedule_trigger", "webhook_trigger"}


def find_root_node(nodes: list[WFNode], edges: list[WFEdge], start_node_id: str | None = None) -> WFNode | None:
    """The node with no incoming edge — same "start node" concept generate_script
    uses (app/codegen/engine.py) — or, when there's more than one, whichever root
    matches start_node_id (a workflow's explicitly-designated start, see
    Workflow.startNodeId). None when there's zero roots, or more than one with no
    matching explicit choice — an invalid/incomplete graph a trigger shouldn't try
    to make sense of; codegen reports it clearly if the workflow is ever actually
    run."""
    targets = {e.target for e in edges}
    roots = [n for n in nodes if n.id not in targets]
    if len(roots) == 1:
        return roots[0]
    if start_node_id is not None:
        return next((n for n in roots if n.id == start_node_id), None)
    return None


def _find_pause_points(nodes: list[WFNode], edges: list[WFEdge], start: WFNode) -> list[str]:
    """Labels of every Pause node, and every connector with its breakpoint toggle on,
    reachable from `start` — both stop a running script at a pdb breakpoint() waiting
    for someone to send "continue". Fine for a manual Run (the Run panel can do that),
    fatal for a Schedule/Webhook-triggered run: nothing unattended can ever answer
    that prompt, so the browser process it opened just hangs forever."""
    outgoing: dict[str, list[WFEdge]] = {}
    for e in edges:
        outgoing.setdefault(e.source, []).append(e)
    node_map = {n.id: n for n in nodes}

    found: list[str] = []
    seen = {start.id}
    stack = [start.id]
    while stack:
        node_id = stack.pop()
        node = node_map.get(node_id)
        if node is not None and node.type == "pause":
            found.append(f"Pause node '{node.title or node.id}'")
        for edge in outgoing.get(node_id, []):
            if edge.breakpoint:
                target = node_map.get(edge.target)
                target_label = (target.title or target.id) if target else edge.target
                found.append(f"breakpoint on the connector into '{target_label}'")
            if edge.target not in seen:
                seen.add(edge.target)
                stack.append(edge.target)
    return found


def validate_publishable(workflow: Workflow) -> None:
    """Raises ValueError with a user-facing message when the workflow can't be
    published as-is — used by the publish endpoint to reject with a clear 400
    instead of silently registering a trigger that will never fire."""
    root = find_root_node(workflow.nodes, workflow.edges, workflow.startNodeId)
    if root is None:
        raise ValueError("Workflow needs exactly one start node before it can be published")
    if root.type not in TRIGGER_NODE_TYPES:
        raise ValueError("Workflow's start node must be a Schedule Trigger or a Webhook trigger to be published")

    pause_points = _find_pause_points(workflow.nodes, workflow.edges, root)
    if pause_points:
        names = "; ".join(pause_points)
        raise ValueError(
            f"Workflow can't be published while it can reach: {names}. An unattended "
            "scheduled/webhook run has nobody to click Continue, so it would hang "
            "forever — remove the Pause node or turn off the breakpoint on that "
            "connector first."
        )

    if root.type == "schedule_trigger":
        from app.execution.scheduler import _build_trigger

        _build_trigger(root)
    else:
        from app.execution.webhook_registry import validate_webhook_node

        validate_webhook_node(root)
