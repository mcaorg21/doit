from app.codegen.context import CodegenContext
from app.codegen.template_utils import resolve_credential_value, validate_identifier
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_totp(ctx: CodegenContext) -> str:
    secret_expr = resolve_credential_value(ctx, "credentialId", "2FA Secret")
    result_var = validate_identifier(ctx.params.get("resultVar"), ctx, "Result Variable")

    lines = [
        "import pyotp",
        f"{result_var} = pyotp.TOTP({secret_expr}).now()",
        f'print(f"[{ctx.node_label}] {result_var} = " + {result_var})',
    ]
    return "\n".join(lines)


register(
    NodeSpec(
        type="totp",
        label="2FA Code (TOTP)",
        category="function",
        description=(
            "Generates the current 2FA/TOTP code (via pyotp) from a secret stored as a credential — "
            "register the site's T2FA_SECRET as a Credential first (any Type name, e.g. \"totp\"), then "
            "pick it here. Stores the 6-digit code in a variable, ready to fill into the login form."
        ),
        example='Generates the current 6-digit code from the stored 2FA secret',
        icon="shield-check",
        params=[
            ParamField(
                key="credentialId",
                label="2FA Secret (T2FA_SECRET)",
                type="text",
                required=True,
                credentialType="totp",
            ),
            ParamField(
                key="resultVar",
                label="Result Variable",
                type="text",
                required=True,
                placeholder="totp_code",
                producesVariable=True,
            ),
        ],
        codegen=codegen_totp,
    )
)
