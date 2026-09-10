import { api } from './client'

interface LaunchResult {
  launched: boolean
  detail?: string | null
  notify: boolean
}

export const launchApi = {
  terminal: (projectId?: string, workflowId?: string) =>
    api.post<LaunchResult>('/api/launch/terminal', { projectId, workflowId }),
  claudeDesktop: () => api.post<LaunchResult>('/api/launch/claude-desktop', {}),
}
