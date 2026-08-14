from fastapi import APIRouter, HTTPException, Response

from app.models.backup import BackupConfigInput, BackupResult, BackupStatus, RestorePreview, RestoreResult
from app.services import postgres_backup
from app.services.backup_orchestrator import preview_remote, run_backup, run_restore
from app.services.postgres_backup import BackupError
from app.storage import backup_config_store

# Deliberately NOT nested under /api/projects/{project_id}/... — this is global
# scope by explicit design (one Postgres connection for the whole app), unlike
# credentials/folders/workflows which are all per-project.
router = APIRouter(prefix="/api/backup", tags=["backup"])


def _status_from_config(config) -> BackupStatus:
    if config is None:
        return BackupStatus(configured=False)
    return BackupStatus(
        configured=True,
        connectionString=config.connectionString,
        lastBackupAt=config.lastBackupAt,
        lastBackupCounts=config.lastBackupCounts,
        lastRestoreAt=config.lastRestoreAt,
    )


@router.get("/status", response_model=BackupStatus)
def get_status():
    return _status_from_config(backup_config_store.get_config())


@router.post("/config", response_model=BackupStatus)
def save_config(payload: BackupConfigInput):
    connection_string = payload.connectionString.strip()
    if not connection_string:
        raise HTTPException(status_code=422, detail="Connection string is required")
    try:
        # Test the connection and create the tables *before* persisting — a bad
        # connection string should never get saved as if it worked.
        with postgres_backup.connect(connection_string) as conn:
            postgres_backup.ensure_schema(conn)
    except BackupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    config = backup_config_store.save_config(connection_string)
    return _status_from_config(config)


@router.delete("/config", status_code=204)
def delete_config():
    backup_config_store.delete_config()
    return Response(status_code=204)


@router.post("/run", response_model=BackupResult)
def backup_now():
    try:
        return run_backup()
    except BackupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/preview", response_model=RestorePreview)
def preview():
    try:
        return preview_remote()
    except BackupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/restore", response_model=RestoreResult)
def restore():
    try:
        return run_restore()
    except BackupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
