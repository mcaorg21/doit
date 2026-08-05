from datetime import datetime

from pydantic import BaseModel


class Folder(BaseModel):
    id: str
    projectId: str
    name: str
    parentId: str | None = None
    createdAt: datetime
    updatedAt: datetime


class FolderCreate(BaseModel):
    name: str
    parentId: str | None = None


class FolderUpdate(BaseModel):
    name: str
