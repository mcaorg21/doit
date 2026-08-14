import json

from fastapi import HTTPException

from app.config import project_dir
from app.models.folder import Folder, FolderCreate, FolderUpdate
from app.models.project import now_utc
from app.storage import project_store
from app.storage.ids import gen_id

# Folders are lightweight and always fetched as a full per-project list anyway (the
# frontend needs the whole tree to render breadcrumbs/nesting), so — unlike
# workflows/projects — they live in one manifest file instead of one file each.


def _folders_file(project_id: str):
    return project_dir(project_id) / "folders.json"


def _read_all(project_id: str) -> list[Folder]:
    f = _folders_file(project_id)
    if not f.exists():
        return []
    raw = json.loads(f.read_text(encoding="utf-8"))
    return [Folder.model_validate(item) for item in raw]


def _write_all(project_id: str, folders: list[Folder]) -> None:
    _folders_file(project_id).write_text(
        json.dumps([f.model_dump(mode="json") for f in folders], indent=2), encoding="utf-8"
    )


def put_folders(project_id: str, folders: list[Folder]) -> None:
    """Overwrites the whole manifest verbatim — used by restore
    (app/services/backup_orchestrator.py) to reconstruct a project's folders exactly
    as they were in the backup."""
    _write_all(project_id, folders)


def list_folders(project_id: str) -> list[Folder]:
    project_store.get_project(project_id)  # 404 if project missing
    return _read_all(project_id)


def create_folder(project_id: str, payload: FolderCreate) -> Folder:
    project_store.get_project(project_id)
    folders = _read_all(project_id)
    if payload.parentId is not None and not any(f.id == payload.parentId for f in folders):
        raise HTTPException(status_code=404, detail=f"Folder '{payload.parentId}' not found")

    ts = now_utc()
    folder = Folder(
        id=gen_id("fold"),
        projectId=project_id,
        name=payload.name,
        parentId=payload.parentId,
        createdAt=ts,
        updatedAt=ts,
    )
    folders.append(folder)
    _write_all(project_id, folders)
    project_store.touch_project(project_id)
    return folder


def rename_folder(project_id: str, folder_id: str, payload: FolderUpdate) -> Folder:
    folders = _read_all(project_id)
    for i, f in enumerate(folders):
        if f.id == folder_id:
            updated = f.model_copy(update={"name": payload.name, "updatedAt": now_utc()})
            folders[i] = updated
            _write_all(project_id, folders)
            project_store.touch_project(project_id)
            return updated
    raise HTTPException(status_code=404, detail=f"Folder '{folder_id}' not found")


def delete_folder(project_id: str, folder_id: str) -> None:
    from app.storage import workflow_store

    folders = _read_all(project_id)
    if not any(f.id == folder_id for f in folders):
        raise HTTPException(status_code=404, detail=f"Folder '{folder_id}' not found")
    if any(f.parentId == folder_id for f in folders):
        raise HTTPException(status_code=400, detail="Folder still has subfolders — delete or move them first")
    if any(w.folderId == folder_id for w in workflow_store.list_workflows(project_id)):
        raise HTTPException(status_code=400, detail="Folder still has workflows — delete or move them first")

    folders = [f for f in folders if f.id != folder_id]
    _write_all(project_id, folders)
    project_store.touch_project(project_id)
