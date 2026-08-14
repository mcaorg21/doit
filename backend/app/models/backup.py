from datetime import datetime

from pydantic import BaseModel


class BackupCounts(BaseModel):
    projects: int
    folders: int
    workflows: int
    credentials: int
    runs: int


class BackupConfig(BaseModel):
    connectionString: str
    """Plain Postgres connection string. Stored in plain JSON like Credential.value
    (app/models/credential.py) — same reasoning: this app has no auth/multi-tenancy
    boundary to protect, so encrypting it at rest wouldn't buy anything."""
    createdAt: datetime
    updatedAt: datetime
    lastBackupAt: datetime | None = None
    lastBackupCounts: BackupCounts | None = None
    lastRestoreAt: datetime | None = None


class BackupConfigInput(BaseModel):
    connectionString: str


class BackupStatus(BaseModel):
    configured: bool
    connectionString: str | None = None
    lastBackupAt: datetime | None = None
    lastBackupCounts: BackupCounts | None = None
    lastRestoreAt: datetime | None = None


class BackupResult(BaseModel):
    counts: BackupCounts
    warnings: list[str] = []
    finishedAt: datetime


class RestorePreview(BaseModel):
    counts: BackupCounts
    lastUpdatedAt: dict[str, datetime | None]


class RestoreResult(BaseModel):
    counts: BackupCounts
    finishedAt: datetime
