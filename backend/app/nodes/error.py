from app.codegen.context import CodegenContext
from app.codegen.template_utils import render_template_expr
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_error(ctx: CodegenContext) -> str:
    message_raw = (ctx.params.get("message") or "").strip() or "Error node reached"
    message_expr = render_template_expr(message_raw, ctx)
    return (
        # __WORKFLOW_MARK_ERROR__ (parsed by app/execution/runner.py's _stream_output)
        # unpublishes this workflow and flags it hasError — unconditionally, unlike the
        # runner's own auto-unpublish-on-failure logic, which only fires for unattended
        # (Schedule/Webhook) runs. This node means it every time it's reached, no matter
        # who/what triggered the run.
        f'print("__WORKFLOW_MARK_ERROR__" + json.dumps({{"nodeId": {ctx.node_id!r}, "message": {message_expr}}}, default=str))\n'
        # Then actually fails the run the same way any other node's failure would — the
        # engine's own try/except wrap around this fragment (see engine.py) catches it,
        # prints __NODE_ERROR__ and drops into breakpoint(), so a manual run stops right
        # here for inspection instead of silently continuing past a deliberate failure.
        f"raise RuntimeError({message_expr})"
    )


register(
    NodeSpec(
        type="error",
        label="Error",
        category="logic",
        description=(
            "Deliberately fails the run right here: unpublishes this workflow and flags it with a red "
            "error state — shown on this workflow's own Publish button AND on its row in the workflow "
            "list — then raises, so the run stops at this node the same way any other failure would. "
            "Unlike an ordinary crash (which only auto-unpublishes on an unattended Schedule/Webhook "
            "run), this node always marks the workflow broken, regardless of how the run was started. "
            "Use it to catch an unexpected/invalid case on purpose, e.g. at the end of an IF branch."
        ),
        example="Fails with 'Unexpected account status', unpublishing this workflow",
        icon="octagon-alert",
        params=[
            ParamField(
                key="message",
                label="Error Message",
                type="text",
                supportsTemplate=True,
                placeholder="Unexpected state — failing on purpose",
            ),
        ],
        codegen=codegen_error,
    )
)
