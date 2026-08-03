import { api } from './client'
import type { Project } from '../types/workflow'

export const projectsApi = {
  list: () => api.get<Project[]>('/api/projects'),
  create: (name: string) => api.post<Project>('/api/projects', { name }),
  get: (id: string) => api.get<Project>(`/api/projects/${id}`),
  rename: (id: string, name: string) => api.patch<Project>(`/api/projects/${id}`, { name }),
  remove: (id: string) => api.delete<void>(`/api/projects/${id}`),
}
