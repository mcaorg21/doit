import { api } from './client'
import type { Folder } from '../types/workflow'

export const foldersApi = {
  list: (projectId: string) => api.get<Folder[]>(`/api/projects/${projectId}/folders`),
  create: (projectId: string, name: string, parentId: string | null) =>
    api.post<Folder>(`/api/projects/${projectId}/folders`, { name, parentId }),
  rename: (projectId: string, folderId: string, name: string) =>
    api.put<Folder>(`/api/projects/${projectId}/folders/${folderId}`, { name }),
  remove: (projectId: string, folderId: string) =>
    api.delete<void>(`/api/projects/${projectId}/folders/${folderId}`),
}
