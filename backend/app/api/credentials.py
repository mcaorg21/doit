import json
from datetime import datetime, timezone

from fastapi import APIRouter

from app.config import cookies_dir_for_credential
from app.models.credential import Credential, CredentialCookiesStatus, CredentialCreate, CredentialUpdate
from app.storage import credential_store

router = APIRouter(prefix="/api/projects/{project_id}/credentials", tags=["credentials"])


@router.get("", response_model=list[Credential])
def list_credentials(project_id: str):
    return credential_store.list_credentials(project_id)


@router.post("", response_model=Credential)
def create_credential(project_id: str, payload: CredentialCreate):
    return credential_store.create_credential(project_id, payload)


@router.put("/{credential_id}", response_model=Credential)
def update_credential(project_id: str, credential_id: str, payload: CredentialUpdate):
    return credential_store.update_credential(project_id, credential_id, payload)


@router.delete("/{credential_id}", status_code=204)
def delete_credential(project_id: str, credential_id: str):
    credential_store.delete_credential(project_id, credential_id)


@router.get("/{credential_id}/cookies", response_model=CredentialCookiesStatus)
def get_credential_cookies_status(project_id: str, credential_id: str):
    """Whether a Login/Microsoft Login node (or a Save Cookies/Load Cookies node
    pointed at this credential) has a saved session for it — see app/nodes/login.py
    and app/config.py::cookies_dir_for_credential."""
    credential_store.get_credential(project_id, credential_id)  # 404 if missing
    path = cookies_dir_for_credential(project_id, credential_id) / "cookies.json"
    if not path.exists():
        return CredentialCookiesStatus(exists=False)
    try:
        count = len(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        count = None
    saved_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return CredentialCookiesStatus(exists=True, count=count, savedAt=saved_at)


@router.delete("/{credential_id}/cookies", status_code=204)
def delete_credential_cookies(project_id: str, credential_id: str):
    """Clears the saved session so the next run logs in fresh — e.g. after a password
    change, or to force a clean re-login for debugging."""
    credential_store.get_credential(project_id, credential_id)  # 404 if missing
    path = cookies_dir_for_credential(project_id, credential_id) / "cookies.json"
    if path.exists():
        path.unlink()
