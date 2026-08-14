import { api } from './client'
import type { BackupResult, BackupStatus, RestorePreview, RestoreResult } from '../types/workflow'

export const backupApi = {
  getStatus: () => api.get<BackupStatus>('/api/backup/status'),
  saveConfig: (connectionString: string) => api.post<BackupStatus>('/api/backup/config', { connectionString }),
  removeConfig: () => api.delete<void>('/api/backup/config'),
  runBackup: () => api.post<BackupResult>('/api/backup/run'),
  preview: () => api.get<RestorePreview>('/api/backup/preview'),
  restore: () => api.post<RestoreResult>('/api/backup/restore'),
}
