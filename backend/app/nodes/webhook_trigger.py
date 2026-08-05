from app.codegen.context import CodegenContext
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_webhook_trigger(ctx: CodegenContext) -> str:
    # Same idea as Schedule Trigger's codegen: purely a marker. Incoming HTTP calls
    # are matched to a workflow by app/execution/webhook_registry.py, which is what
    # actually decides *when* this runs — this node's own code has nothing to do.
    return f'print("[{ctx.node_label}] webhook triggered")'


register(
    NodeSpec(
        type="webhook_trigger",
        label="Webhook",
        category="trigger",
        description=(
            "Starts this workflow when an HTTP request hits /api/webhooks/<path>/<secret>. "
            "The secret is generated automatically so the URL can't be guessed — use the "
            "regenerate button to rotate it. Must be the workflow's start node, and only "
            "fires while the workflow is published (topbar toggle) — same as the Schedule "
            "Trigger."
        ),
        icon="webhook",
        params=[
            ParamField(
                key="method",
                label="HTTP Method",
                type="select",
                default="POST",
                options=[
                    {"value": "GET", "label": "GET"},
                    {"value": "POST", "label": "POST"},
                ],
            ),
            ParamField(
                key="path",
                label="Path",
                type="text",
                required=True,
                placeholder="my-webhook",
            ),
            ParamField(
                key="secret",
                label="Secret",
                type="text",
                required=True,
                autoGenerate=True,
            ),
        ],
        codegen=codegen_webhook_trigger,
    )
)
