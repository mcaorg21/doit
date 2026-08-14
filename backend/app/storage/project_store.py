from fastapi import HTTPException

from app.config import PROJECTS_DIR, project_dir, workflows_dir, runs_dir
from app.models.project import Project, ProjectCreate, ProjectUpdate, now_utc
from app.storage.ids import gen_id


def _project_file(project_id: str):
    return project_dir(project_id) / "project.json"


def list_projects() -> list[Project]:
    if not PROJECTS_DIR.exists():
        return []
    projects = []
    for child in sorted(PROJECTS_DIR.iterdir()):
        pfile = child / "project.json"
        if pfile.exists():
            projects.append(Project.model_validate_json(pfile.read_text(encoding="utf-8")))
    projects.sort(key=lambda p: p.updatedAt, reverse=True)
    return projects


def get_project(project_id: str) -> Project:
    pfile = _project_file(project_id)
    if not pfile.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return Project.model_validate_json(pfile.read_text(encoding="utf-8"))


def create_project(payload: ProjectCreate) -> Project:
    project_id = gen_id("proj")
    ts = now_utc()
    project = Project(id=project_id, name=payload.name, createdAt=ts, updatedAt=ts)
    project_dir(project_id).mkdir(parents=True, exist_ok=True)
    workflows_dir(project_id).mkdir(parents=True, exist_ok=True)
    runs_dir(project_id).mkdir(parents=True, exist_ok=True)
    _project_file(project_id).write_text(project.model_dump_json(indent=2), encoding="utf-8")
    return project


def put_project(project: Project) -> None:
    """Writes a project verbatim, preserving its id/timestamps as-is — used by
    restore (app/services/backup_orchestrator.py) to reconstruct a project exactly
    as it was in the backup, unlike create_project() which always mints a new id."""
    project_dir(project.id).mkdir(parents=True, exist_ok=True)
    workflows_dir(project.id).mkdir(parents=True, exist_ok=True)
    runs_dir(project.id).mkdir(parents=True, exist_ok=True)
    _project_file(project.id).write_text(project.model_dump_json(indent=2), encoding="utf-8")


def update_project(project_id: str, payload: ProjectUpdate) -> Project:
    project = get_project(project_id)
    project.name = payload.name
    project.updatedAt = now_utc()
    _project_file(project_id).write_text(project.model_dump_json(indent=2), encoding="utf-8")
    return project


def touch_project(project_id: str) -> None:
    project = get_project(project_id)
    project.updatedAt = now_utc()
    _project_file(project_id).write_text(project.model_dump_json(indent=2), encoding="utf-8")


def delete_project(project_id: str) -> None:
    import shutil

    pdir = project_dir(project_id)
    if not pdir.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")

    # Local imports: workflow_store imports this module at load time (touch_project),
    # and execution.scheduler/webhook_registry import workflow_store — importing
    # either eagerly here would be circular.
    from app.execution import scheduler, webhook_registry
    from app.storage import workflow_store

    for workflow in workflow_store.list_workflows(project_id):
        scheduler.remove_workflow_job(workflow.id)
        webhook_registry.remove_workflow(workflow.id)

    shutil.rmtree(pdir)
