from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import HTTPException

from app.execution.triggers import find_root_node
from app.models.workflow import WFNode, Workflow

_INTERVAL_UNITS = {"seconds", "minutes", "hours", "days"}

_scheduler: AsyncIOScheduler | None = None


def _build_trigger(node: WFNode):
    params = node.params or {}
    mode = params.get("mode", "interval")

    if mode == "cron":
        expr = str(params.get("cronExpression") or "").strip()
        if not expr:
            raise ValueError("Cron Expression is empty")
        parts = expr.split()
        if len(parts) == 6:
            second, minute, hour, day, month, dow = parts
        elif len(parts) == 5:
            second = "0"
            minute, hour, day, month, dow = parts
        else:
            raise ValueError(
                f"Cron Expression must have 5 fields (min hour day month weekday) or 6 "
                f"fields (sec min hour day month weekday), got {len(parts)}: {expr!r}"
            )
        try:
            return CronTrigger(second=second, minute=minute, hour=hour, day=day, month=month, day_of_week=dow)
        except ValueError as exc:
            raise ValueError(f"Invalid Cron Expression {expr!r}: {exc}") from exc

    unit = params.get("intervalUnit", "minutes")
    if unit not in _INTERVAL_UNITS:
        raise ValueError(f"Invalid interval unit {unit!r}")
    try:
        value = float(params.get("intervalValue") or 1)
    except (TypeError, ValueError):
        raise ValueError("Interval value must be a number")
    if value <= 0:
        raise ValueError("Interval value must be greater than 0")
    return IntervalTrigger(**{unit: value})


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.start()
    sync_all()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def remove_workflow_job(workflow_id: str) -> None:
    if _scheduler is None:
        return
    try:
        _scheduler.remove_job(workflow_id)
    except JobLookupError:
        pass


def sync_workflow(project_id: str, workflow: Workflow) -> None:
    """Adds/updates/removes this workflow's scheduled job to match its current
    published flag and Schedule Trigger params. Called after every save, publish
    toggle, and once for every workflow at backend startup — safe (and cheap) to call
    even when nothing actually changed."""
    if _scheduler is None:
        return
    remove_workflow_job(workflow.id)
    if not workflow.published:
        return

    root = find_root_node(workflow.nodes, workflow.edges, workflow.startNodeId)
    if root is None or root.type != "schedule_trigger":
        print(f"[scheduler] workflow '{workflow.name}' ({workflow.id}) is published but has no Schedule Trigger start node — not scheduled")
        return
    try:
        trigger = _build_trigger(root)
    except ValueError as exc:
        print(f"[scheduler] workflow '{workflow.name}' ({workflow.id}): {exc} — not scheduled")
        return

    _scheduler.add_job(
        _run_workflow_job,
        trigger=trigger,
        id=workflow.id,
        args=[project_id, workflow.id],
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    print(f"[scheduler] scheduled workflow '{workflow.name}' ({workflow.id})")


def sync_all() -> None:
    from app.storage import project_store, workflow_store

    for project in project_store.list_projects():
        for workflow in workflow_store.list_workflows(project.id):
            sync_workflow(project.id, workflow)


async def _run_workflow_job(project_id: str, workflow_id: str) -> None:
    from app.codegen.context import CodegenError
    from app.codegen.engine import generate_script
    from app.execution.runner import start_run
    from app.storage import workflow_store

    try:
        workflow = workflow_store.get_workflow(project_id, workflow_id)
    except HTTPException:
        print(f"[scheduler] workflow '{workflow_id}' no longer exists — removing its job")
        remove_workflow_job(workflow_id)
        return

    if not workflow.published:
        # Unpublished since this job was scheduled but not yet resynced — bail rather
        # than run a workflow the user just took down.
        return

    try:
        script = generate_script(
            workflow.nodes, workflow.edges, project_id, start_node_id=workflow.startNodeId, workflow_id=workflow_id
        )
    except CodegenError as exc:
        print(f"[scheduler] workflow '{workflow.name}' ({workflow_id}) failed to generate: {exc}")
        return

    print(f"[scheduler] firing scheduled run for workflow '{workflow.name}' ({workflow_id})")
    await start_run(project_id, workflow_id, script, unattended=True)
