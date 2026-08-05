from app.models.workflow import WFEdge, WFNode, Workflow

# Node types allowed to be a workflow's start node when it's published — anything
# else can only ever be run manually (the Run button), never by the scheduler or a
# webhook call.
TRIGGER_NODE_TYPES = {"schedule_trigger", "webhook_trigger"}


def find_root_node(nodes: list[WFNode], edges: list[WFEdge]) -> WFNode | None:
    """The node with no incoming edge — same "start node" concept generate_script
    uses — or None when there's zero or more than one (an invalid/incomplete graph
    a trigger shouldn't try to make sense of; codegen reports it clearly if the
    workflow is ever actually run)."""
    targets = {e.target for e in edges}
    roots = [n for n in nodes if n.id not in targets]
    return roots[0] if len(roots) == 1 else None


def validate_publishable(workflow: Workflow) -> None:
    """Raises ValueError with a user-facing message when the workflow can't be
    published as-is — used by the publish endpoint to reject with a clear 400
    instead of silently registering a trigger that will never fire."""
    root = find_root_node(workflow.nodes, workflow.edges)
    if root is None:
        raise ValueError("Workflow needs exactly one start node before it can be published")
    if root.type not in TRIGGER_NODE_TYPES:
        raise ValueError("Workflow's start node must be a Schedule Trigger or a Webhook trigger to be published")

    if root.type == "schedule_trigger":
        from app.execution.scheduler import _build_trigger

        _build_trigger(root)
    else:
        from app.execution.webhook_registry import validate_webhook_node

        validate_webhook_node(root)
