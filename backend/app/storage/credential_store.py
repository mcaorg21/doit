import json

from fastapi import HTTPException

from app.config import project_dir
from app.models.credential import Credential, CredentialCreate, CredentialUpdate
from app.models.project import now_utc
from app.storage import project_store
from app.storage.ids import gen_id

# Same one-manifest-file-per-project shape as folder_store.py — credentials are
# lightweight and always fetched as a full per-project list (a node's credential
# picker needs the whole set to filter/search), so there's no benefit to a
# one-file-per-credential layout here.


def _credentials_file(project_id: str):
    return project_dir(project_id) / "credentials.json"


def _read_all(project_id: str) -> list[Credential]:
    f = _credentials_file(project_id)
    if not f.exists():
        return []
    raw = json.loads(f.read_text(encoding="utf-8"))
    return [Credential.model_validate(item) for item in raw]


def _write_all(project_id: str, credentials: list[Credential]) -> None:
    _credentials_file(project_id).write_text(
        json.dumps([c.model_dump(mode="json") for c in credentials], indent=2), encoding="utf-8"
    )


def put_credentials(project_id: str, credentials: list[Credential]) -> None:
    """Overwrites the whole manifest verbatim — used by restore
    (app/services/backup_orchestrator.py) to reconstruct a project's credentials
    exactly as they were in the backup."""
    _write_all(project_id, credentials)


def list_credentials(project_id: str) -> list[Credential]:
    project_store.get_project(project_id)  # 404 if project missing
    return _read_all(project_id)


def get_credential(project_id: str, credential_id: str) -> Credential:
    for c in _read_all(project_id):
        if c.id == credential_id:
            return c
    raise HTTPException(status_code=404, detail=f"Credential '{credential_id}' not found")


def create_credential(project_id: str, payload: CredentialCreate) -> Credential:
    project_store.get_project(project_id)
    credentials = _read_all(project_id)
    ts = now_utc()
    credential = Credential(
        id=gen_id("cred"),
        projectId=project_id,
        name=payload.name,
        type=payload.type,
        value=payload.value,
        createdAt=ts,
        updatedAt=ts,
    )
    credentials.append(credential)
    _write_all(project_id, credentials)
    project_store.touch_project(project_id)
    return credential


def update_credential(project_id: str, credential_id: str, payload: CredentialUpdate) -> Credential:
    credentials = _read_all(project_id)
    for i, c in enumerate(credentials):
        if c.id == credential_id:
            updated = c.model_copy(
                update={"name": payload.name, "type": payload.type, "value": payload.value, "updatedAt": now_utc()}
            )
            credentials[i] = updated
            _write_all(project_id, credentials)
            project_store.touch_project(project_id)
            return updated
    raise HTTPException(status_code=404, detail=f"Credential '{credential_id}' not found")


def delete_credential(project_id: str, credential_id: str) -> None:
    credentials = _read_all(project_id)
    if not any(c.id == credential_id for c in credentials):
        raise HTTPException(status_code=404, detail=f"Credential '{credential_id}' not found")
    credentials = [c for c in credentials if c.id != credential_id]
    _write_all(project_id, credentials)
    project_store.touch_project(project_id)
