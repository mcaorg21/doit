import { api } from './client'
import type { Credential } from '../types/workflow'

export const credentialsApi = {
  list: (projectId: string) => api.get<Credential[]>(`/api/projects/${projectId}/credentials`),
  create: (projectId: string, name: string, type: string, value: string) =>
    api.post<Credential>(`/api/projects/${projectId}/credentials`, { name, type, value }),
  update: (projectId: string, credentialId: string, name: string, type: string, value: string) =>
    api.put<Credential>(`/api/projects/${projectId}/credentials/${credentialId}`, { name, type, value }),
  remove: (projectId: string, credentialId: string) =>
    api.delete<void>(`/api/projects/${projectId}/credentials/${credentialId}`),
}
