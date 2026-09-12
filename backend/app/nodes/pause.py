from app.codegen.context import CodegenContext
from app.nodes.base import NodeSpec
from app.nodes.registry import register


def codegen_pause(ctx: CodegenContext) -> str:
    # __NODE_PAUSED__ (parsed by frontend/src/editor/RunPanel.tsx, same pattern as
    # __NODE_START__/__NODE_ERROR__) lets the editor mark this node red instead of the
    # green "still executing" pulse while the run is genuinely stopped at pdb waiting
    # for a human.
    return (
        f'print("__NODE_PAUSED__{ctx.node_id}")\n'
        f'print("[{ctx.node_label}] paused — use pdb commands to inspect state (c to continue, n to step, p <expr>...)")\n'
        "breakpoint()"
    )


register(
    NodeSpec(
        type="pause",
        label="Pause",
        category="logic",
        description=(
            "Drops into pdb (pdb.set_trace()) right here, pausing the script. "
            "Same mechanism as toggling a breakpoint on a connector, but as an explicit "
            "node — use the Run panel's Continue button or type a pdb command to resume."
        ),
        example='Stops the run here so you can inspect the page with pdb',
        icon="pause",
        params=[],
        codegen=codegen_pause,
    )
)
