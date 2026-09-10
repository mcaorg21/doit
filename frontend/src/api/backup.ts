import { api } from './client'
import type { BackupResult, BackupStatus, RestorePreview, RestoreResult } from '../types/workflow'

export const backupApi = {
  getStatus: (projectId: string) => api.get<BackupStatus>(`/api/projects/${projectId}/backup/status`),
  saveConfig: (projectId: string, connectionString: string) =>
    api.post<BackupStatus>(`/api/projects/${projectId}/backup/config`, { connectionString }),
  removeConfig: (projectId: string) => api.delete<void>(`/api/projects/${projectId}/backup/config`),
  runBackup: (projectId: string) => api.post<BackupResult>(`/api/projects/${projectId}/backup/run`),
  preview: (projectId: string) => api.get<RestorePreview>(`/api/projects/${projectId}/backup/preview`),
  restore: (projectId: string) => api.post<RestoreResult>(`/api/projects/${projectId}/backup/restore`),
}
