from fastapi import APIRouter

from app.models.folder import Folder, FolderCreate, FolderUpdate
from app.storage import folder_store

router = APIRouter(prefix="/api/projects/{project_id}/folders", tags=["folders"])


@router.get("", response_model=list[Folder])
def list_folders(project_id: str):
    return folder_store.list_folders(project_id)


@router.post("", response_model=Folder)
def create_folder(project_id: str, payload: FolderCreate):
    return folder_store.create_folder(project_id, payload)


@router.put("/{folder_id}", response_model=Folder)
def rename_folder(project_id: str, folder_id: str, payload: FolderUpdate):
    return folder_store.rename_folder(project_id, folder_id, payload)


@router.delete("/{folder_id}", status_code=204)
def delete_folder(project_id: str, folder_id: str):
    folder_store.delete_folder(project_id, folder_id)
