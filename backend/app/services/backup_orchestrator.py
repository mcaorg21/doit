"""Orchestration for backup/restore — owns everything local-file-related (walking
data/projects/<id>/, writing it back), delegating all actual Postgres work to
app/services/postgres_backup.py. Direct analogue of
app/services/workflow_reconstructor.py's split from app/services/llm_providers.py.

Scoped per project (see app/storage/backup_config_store.py) — each call operates on
exactly one project's local files and exactly one project's rows in the shared
automation_* tables (via project_id, or workflow_id for runs, which have no
project_id column of their own).
"""

import shutil

from app.config import project_dir
from app.models.backup import BackupCounts, BackupResult, RestorePreview, RestoreResult
from app.models.credential import Credential
from app.models.folder import Folder
from app.models.project import Project, now_utc
from app.models.run import RunRecord
from app.models.workflow import Workflow
from app.services import postgres_backup
from app.services.postgres_backup import BackupError
from app.storage import backup_config_store, credential_store, folder_store, project_store, run_store, workflow_store


def _require_config(project_id: str):
    config = backup_config_store.get_config(project_id)
    if config is None:
        raise BackupError("No Postgres connection configured yet for this project — save one first")
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


def run_backup(project_id: str) -> BackupResult:
    config = _require_config(project_id)
    project = project_store.get_project(project_id)  # 404 if missing

    project_row = _project_row(project)
    folder_rows = [_folder_row(f) for f in folder_store.list_folders(project_id)]
    workflow_rows = [_workflow_row(w) for w in workflow_store.list_workflows(project_id)]
    credential_rows = [_credential_row(c) for c in credential_store.list_credentials(project_id)]
    run_rows = [_run_row(r) for r in run_store.list_runs(project_id)]

    with postgres_backup.connect(config.connectionString) as conn:
        postgres_backup.ensure_schema(conn)
        with conn.transaction():
            postgres_backup.upsert_projects(conn, [project_row])
            postgres_backup.upsert_folders(conn, folder_rows)
            postgres_backup.upsert_workflows(conn, workflow_rows)
            postgres_backup.upsert_credentials(conn, credential_rows)
            postgres_backup.upsert_runs(conn, run_rows)

    counts = BackupCounts(
        projects=1,
        folders=len(folder_rows),
        workflows=len(workflow_rows),
        credentials=len(credential_rows),
        runs=len(run_rows),
    )
    backup_config_store.record_backup(project_id, counts)
    return BackupResult(counts=counts, warnings=[], finishedAt=now_utc())


def preview_remote(project_id: str) -> RestorePreview:
    config = _require_config(project_id)
    with postgres_backup.connect(config.connectionString) as conn:
        counts = postgres_backup.count_rows(conn, project_id)
        last_updated = postgres_backup.last_updated_at(conn, project_id)
    return RestorePreview(counts=counts, lastUpdatedAt=last_updated)


def run_restore(project_id: str) -> RestoreResult:
    config = _require_config(project_id)

    # Fetch everything before touching anything local — if any fetch fails, no local
    # data has been wiped yet.
    with postgres_backup.connect(config.connectionString) as conn:
        project_row = postgres_backup.fetch_project(conn, project_id)
        if project_row is None:
            raise BackupError("No backup found in Postgres for this project yet")
        folder_rows = postgres_backup.fetch_all_folders(conn, project_id)
        workflow_rows = postgres_backup.fetch_all_workflows(conn, project_id)
        credential_rows = postgres_backup.fetch_all_credentials(conn, project_id)
        run_rows = postgres_backup.fetch_all_runs(conn, [w["id"] for w in workflow_rows])

    project = Project.model_validate(project_row)
    folders = [Folder.model_validate(r) for r in folder_rows]
    workflows = [Workflow.model_validate(r) for r in workflow_rows]
    credentials = [Credential.model_validate(r) for r in credential_rows]
    runs = [RunRecord.model_validate(r) for r in run_rows]

    # Restore is a full replace of this project's directory, not a merge — matches
    # the scenario this feature exists for (local files got deleted, pull them back).
    # The backup config itself isn't part of what's backed up (it's local-only
    # connection info, see backup_config_store.py) — preserved verbatim across the
    # wipe instead of being lost with the rest of the directory.
    pdir = project_dir(project_id)
    config_path = pdir / "backup_config.json"
    saved_config_bytes = config_path.read_bytes() if config_path.exists() else None

    if pdir.exists():
        shutil.rmtree(pdir)

    project_store.put_project(project)
    folder_store.put_folders(project_id, folders)
    for workflow in workflows:
        workflow_store.put_workflow(project_id, workflow)
    credential_store.put_credentials(project_id, credentials)
    for run in runs:
        run_store.save_run(project_id, run)

    if saved_config_bytes is not None:
        config_path.write_bytes(saved_config_bytes)

    counts = BackupCounts(
        projects=1,
        folders=len(folders),
        workflows=len(workflows),
        credentials=len(credentials),
        runs=len(runs),
    )
    backup_config_store.record_restore(project_id)
    return RestoreResult(counts=counts, finishedAt=now_utc())
