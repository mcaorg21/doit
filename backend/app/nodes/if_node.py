from app.codegen.context import CodegenContext
from app.codegen.template_utils import validate_identifier
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_if(ctx: CodegenContext) -> str:
    var = validate_identifier(ctx.params.get("conditionVar", ""), ctx, "Variable to test")
    return f"if {var}:"


register(
    NodeSpec(
        type="if",
        label="IF",
        category="logic",
        description=(
            "Branches execution based on a True/False variable set by an earlier node "
            "(e.g. Element Present?). Connect its two outputs to separate true/false paths — "
            "in v1 the branches run independently and don't rejoin."
        ),
        icon="split",
        opens_block=True,
        is_branch=True,
        params=[
            ParamField(key="conditionVar", label="Variable to test", type="text", required=True, placeholder="logged_in"),
        ],
        codegen=codegen_if,
    )
)
