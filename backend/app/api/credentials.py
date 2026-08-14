from fastapi import APIRouter

from app.models.credential import Credential, CredentialCreate, CredentialUpdate
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
