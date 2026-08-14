from app.codegen.context import CodegenContext
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_unknown(ctx: CodegenContext) -> str:
    # Re-emits the original snippet verbatim (already dedented by whatever produced
    # it — see app/services/workflow_reconstructor.py) so a workflow reconstructed
    # from an imported .py stays runnable immediately, even before this placeholder
    # is replaced with a proper typed node.
    code = str(ctx.params.get("code") or "pass").strip("\n")
    return code or "pass"


register(
    NodeSpec(
        type="unknown",
        label="Unknown (from import)",
        category="function",
        description=(
            "Placeholder for a piece of code from an imported Python file that didn't map "
            "to any existing node type. Holds the original snippet verbatim — it still "
            "runs exactly as before — so the reconstructed workflow works immediately. "
            "Replace it with a proper typed node when you get to it."
        ),
        icon="help-circle",
        params=[
            ParamField(key="code", label="Original Python (verbatim)", type="textarea", required=True),
            ParamField(key="sourceHint", label="Why this couldn't be mapped", type="text"),
        ],
        codegen=codegen_unknown,
    )
)
