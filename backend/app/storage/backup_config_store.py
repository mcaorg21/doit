from app.config import BACKUP_CONFIG_FILE
from app.models.backup import BackupConfig, BackupCounts
from app.models.project import now_utc

# Single global object, not a per-project list — unlike every other store in this
# package, there's exactly one of these for the whole app (see the plan's "Escopo:
# global" decision), so it's one file with one JSON object, not a directory.


def get_config() -> BackupConfig | None:
    if not BACKUP_CONFIG_FILE.exists():
        return None
    return BackupConfig.model_validate_json(BACKUP_CONFIG_FILE.read_text(encoding="utf-8"))


def _write(config: BackupConfig) -> None:
    BACKUP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_CONFIG_FILE.write_text(config.model_dump_json(indent=2), encoding="utf-8")


def save_config(connection_string: str) -> BackupConfig:
    existing = get_config()
    ts = now_utc()
    if existing is None:
        config = BackupConfig(connectionString=connection_string, createdAt=ts, updatedAt=ts)
    else:
        config = existing.model_copy(update={"connectionString": connection_string, "updatedAt": ts})
    _write(config)
    return config


def delete_config() -> None:
    if BACKUP_CONFIG_FILE.exists():
        BACKUP_CONFIG_FILE.unlink()


def record_backup(counts: BackupCounts) -> BackupConfig:
    config = get_config()
    if config is None:
        raise RuntimeError("record_backup called with no backup config saved")
    updated = config.model_copy(update={"lastBackupAt": now_utc(), "lastBackupCounts": counts})
    _write(updated)
    return updated


def record_restore() -> BackupConfig:
    config = get_config()
    if config is None:
        raise RuntimeError("record_restore called with no backup config saved")
    updated = config.model_copy(update={"lastRestoreAt": now_utc()})
    _write(updated)
    return updated
