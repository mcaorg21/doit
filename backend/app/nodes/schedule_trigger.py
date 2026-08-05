from app.codegen.context import CodegenContext
from app.nodes.base import NodeSpec, ParamField
from app.nodes.registry import register


def codegen_schedule_trigger(ctx: CodegenContext) -> str:
    # Purely a marker in the generated script — *when* this workflow runs is decided
    # by the backend scheduler (see app/execution/scheduler.py), not by anything this
    # node's own code does. A manual "Run" simply executes the rest of the graph once,
    # same as clicking Run on any other workflow.
    return f'print("[{ctx.node_label}] triggered")'


register(
    NodeSpec(
        type="schedule_trigger",
        label="Schedule Trigger",
        category="trigger",
        description=(
            "Starts this workflow on a recurring schedule — either a simple interval "
            "(every N seconds/minutes/hours/days) or a 5- or 6-field cron expression "
            "(sec min hour day month weekday). Must be the workflow's start node. The "
            "workflow only runs on schedule while Published (topbar toggle)."
        ),
        icon="schedule",
        params=[
            ParamField(
                key="mode",
                label="Schedule Type",
                type="select",
                default="interval",
                options=[
                    {"value": "interval", "label": "Interval"},
                    {"value": "cron", "label": "Cron Expression"},
                ],
            ),
            ParamField(
                key="intervalValue",
                label="Every",
                type="number",
                default=1,
                visibleWhen={"key": "mode", "equals": "interval"},
            ),
            ParamField(
                key="intervalUnit",
                label="Unit",
                type="select",
                default="minutes",
                options=[
                    {"value": "seconds", "label": "Seconds"},
                    {"value": "minutes", "label": "Minutes"},
                    {"value": "hours", "label": "Hours"},
                    {"value": "days", "label": "Days"},
                ],
                visibleWhen={"key": "mode", "equals": "interval"},
            ),
            ParamField(
                key="cronExpression",
                label="Cron Expression",
                type="text",
                default="* * * * *",
                placeholder="* * * * * * (sec min hour day month weekday)",
                visibleWhen={"key": "mode", "equals": "cron"},
            ),
        ],
        codegen=codegen_schedule_trigger,
    )
)
