from app.config import project_dir
from app.models.backup import BackupConfig, BackupCounts
from app.models.project import now_utc

# Per-project, not global — each project keeps its own backup_config.json inside its
# own data/projects/<id>/ directory, same "one manifest file" pattern as
# folder_store.py, so it naturally travels with (and is wiped by) project deletion
# and is never touched by another project's backup/restore.


def _config_file(project_id: str):
    return project_dir(project_id) / "backup_config.json"


def get_config(project_id: str) -> BackupConfig | None:
    f = _config_file(project_id)
    if not f.exists():
        return None
    return BackupConfig.model_validate_json(f.read_text(encoding="utf-8"))


def _write(project_id: str, config: BackupConfig) -> None:
    f = _config_file(project_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(config.model_dump_json(indent=2), encoding="utf-8")


def save_config(project_id: str, connection_string: str) -> BackupConfig:
    existing = get_config(project_id)
    ts = now_utc()
    if existing is None:
        config = BackupConfig(connectionString=connection_string, createdAt=ts, updatedAt=ts)
    else:
        config = existing.model_copy(update={"connectionString": connection_string, "updatedAt": ts})
    _write(project_id, config)
    return config


def delete_config(project_id: str) -> None:
    f = _config_file(project_id)
    if f.exists():
        f.unlink()


def record_backup(project_id: str, counts: BackupCounts) -> BackupConfig:
    config = get_config(project_id)
    if config is None:
        raise RuntimeError("record_backup called with no backup config saved")
    updated = config.model_copy(update={"lastBackupAt": now_utc(), "lastBackupCounts": counts})
    _write(project_id, updated)
    return updated


def record_restore(project_id: str) -> BackupConfig:
    config = get_config(project_id)
    if config is None:
        raise RuntimeError("record_restore called with no backup config saved")
    updated = config.model_copy(update={"lastRestoreAt": now_utc()})
    _write(project_id, updated)
    return updated
