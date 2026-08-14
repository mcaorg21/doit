"""Orchestration for backup/restore — owns everything local-file-related (walking
data/projects/, writing it back), delegating all actual Postgres work to
app/services/postgres_backup.py. Direct analogue of
app/services/workflow_reconstructor.py's split from app/services/llm_providers.py.
"""

import shutil

from app.config import PROJECTS_DIR
from app.models.backup import BackupCounts, BackupResult, RestorePreview, RestoreResult
from app.models.credential import Credential
from app.models.folder import Folder
from app.models.project import Project, now_utc
from app.models.run import RunRecord
from app.models.workflow import Workflow
from app.services import postgres_backup
from app.services.postgres_backup import BackupError
from app.storage import backup_config_store, credential_store, folder_store, project_store, run_store, workflow_store


def _require_config():
    config = backup_config_store.get_config()
    if config is None:
        raise BackupError("No Postgres connection configured yet — save one first")
    return config


def _project_row(p: Project) -> dict:
    return {"id": p.id, "name": p.name, "createdAt": p.createdAt, "updatedAt": p.updatedAt}


def _folder_row(f: Folder) -> dict:
    return {
        "id": f.id,
        "projectId": f.projectId,
        "name": f.name,
        "parentId": f.parentId,
        "createdAt": f.createdAt,
        "updatedAt": f.updatedAt,
    }


def _workflow_row(w: Workflow) -> dict:
    return {
        "id": w.id,
        "projectId": w.projectId,
        "name": w.name,
        "createdAt": w.createdAt,
        "updatedAt": w.updatedAt,
        "published": w.published,
        "folderId": w.folderId,
        "startNodeId": w.startNodeId,
        "nodes": [n.model_dump(mode="json") for n in w.nodes],
        "edges": [e.model_dump(mode="json") for e in w.edges],
    }


def _credential_row(c: Credential) -> dict:
    return {
        "id": c.id,
        "projectId": c.projectId,
        "name": c.name,
        "type": c.type,
        "value": c.value,
        "createdAt": c.createdAt,
        "updatedAt": c.updatedAt,
    }


def _run_row(r: RunRecord) -> dict:
    return {
        "id": r.id,
        "workflowId": r.workflowId,
        "startedAt": r.startedAt,
        "finishedAt": r.finishedAt,
        "status": r.status.value,
        "exitCode": r.exitCode,
        "scriptPath": r.scriptPath,
        "logLines": [line.model_dump(mode="json") for line in r.logLines],
    }


def run_backup() -> BackupResult:
    config = _require_config()
    warnings: list[str] = []

    project_rows: list[dict] = []
    folder_rows: list[dict] = []
    workflow_rows: list[dict] = []
    credential_rows: list[dict] = []
    run_rows: list[dict] = []

    # list_projects() already silently skips any data/projects/* child directory
    # missing project.json (see project_store.py) — the one known orphaned directory
    # on this machine is invisible here exactly as it's invisible everywhere else in
    # the app, no extra directory-walking needed.
    for project in project_store.list_projects():
        try:
            project_rows.append(_project_row(project))
            folder_rows.extend(_folder_row(f) for f in folder_store.list_folders(project.id))
            workflow_rows.extend(_workflow_row(w) for w in workflow_store.list_workflows(project.id))
            credential_rows.extend(_credential_row(c) for c in credential_store.list_credentials(project.id))
            run_rows.extend(_run_row(r) for r in run_store.list_runs(project.id))
        except Exception as exc:  # noqa: BLE001 — one bad project shouldn't abort the whole backup
            warnings.append(f"Project '{project.id}' ({project.name}): skipped — {exc}")

    with postgres_backup.connect(config.connectionString) as conn:
        postgres_backup.ensure_schema(conn)
        with conn.transaction():
            postgres_backup.upsert_projects(conn, project_rows)
            postgres_backup.upsert_folders(conn, folder_rows)
            postgres_backup.upsert_workflows(conn, workflow_rows)
            postgres_backup.upsert_credentials(conn, credential_rows)
            postgres_backup.upsert_runs(conn, run_rows)

    counts = BackupCounts(
        projects=len(project_rows),
        folders=len(folder_rows),
        workflows=len(workflow_rows),
        credentials=len(credential_rows),
        runs=len(run_rows),
    )
    backup_config_store.record_backup(counts)
    return BackupResult(counts=counts, warnings=warnings, finishedAt=now_utc())


def preview_remote() -> RestorePreview:
    config = _require_config()
    with postgres_backup.connect(config.connectionString) as conn:
        counts = postgres_backup.count_rows(conn)
        last_updated = postgres_backup.last_updated_at(conn)
    return RestorePreview(counts=counts, lastUpdatedAt=last_updated)


def run_restore() -> RestoreResult:
    config = _require_config()

    # Fetch everything before touching anything local — if any fetch fails, no local
    # data has been wiped yet.
    with postgres_backup.connect(config.connectionString) as conn:
        project_rows = postgres_backup.fetch_all_projects(conn)
        folder_rows = postgres_backup.fetch_all_folders(conn)
        workflow_rows = postgres_backup.fetch_all_workflows(conn)
        credential_rows = postgres_backup.fetch_all_credentials(conn)
        run_rows = postgres_backup.fetch_all_runs(conn)

    projects = [Project.model_validate(r) for r in project_rows]
    folders = [Folder.model_validate(r) for r in folder_rows]
    workflows = [Workflow.model_validate(r) for r in workflow_rows]
    credentials = [Credential.model_validate(r) for r in credential_rows]
    runs = [RunRecord.model_validate(r) for r in run_rows]

    workflow_to_project = {w.id: w.projectId for w in workflows}

    folders_by_project: dict[str, list[Folder]] = {}
    for f in folders:
        folders_by_project.setdefault(f.projectId, []).append(f)

    workflows_by_project: dict[str, list[Workflow]] = {}
    for w in workflows:
        workflows_by_project.setdefault(w.projectId, []).append(w)

    credentials_by_project: dict[str, list[Credential]] = {}
    for c in credentials:
        credentials_by_project.setdefault(c.projectId, []).append(c)

    runs_by_project: dict[str, list[RunRecord]] = {}
    for r in runs:
        project_id = workflow_to_project.get(r.workflowId)
        if project_id is not None:
            runs_by_project.setdefault(project_id, []).append(r)
        # Runs whose workflow no longer exists can't be placed under any project
        # directory — dropped, same as the app already tolerating orphaned data.

    # Restore is a full replace, not a merge — matches the scenario this feature
    # exists for (local files got deleted, pull everything back).
    if PROJECTS_DIR.exists():
        shutil.rmtree(PROJECTS_DIR)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    for project in projects:
        project_store.put_project(project)
        folder_store.put_folders(project.id, folders_by_project.get(project.id, []))
        for workflow in workflows_by_project.get(project.id, []):
            workflow_store.put_workflow(project.id, workflow)
        credential_store.put_credentials(project.id, credentials_by_project.get(project.id, []))
        for run in runs_by_project.get(project.id, []):
            run_store.save_run(project.id, run)

    counts = BackupCounts(
        projects=len(projects),
        folders=len(folders),
        workflows=len(workflows),
        credentials=len(credentials),
        runs=len(runs),
    )
    backup_config_store.record_restore()
    return RestoreResult(counts=counts, finishedAt=now_utc())
