from app.codegen.context import CodegenContext
from app.nodes.base import NodeSpec
from app.nodes.registry import register


def codegen_pause(ctx: CodegenContext) -> str:
    return (
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
        icon="pause",
        params=[],
        codegen=codegen_pause,
    )
)
