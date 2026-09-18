import { api } from './client'

export type CliProvider = 'claude' | 'codex'

interface LaunchResult {
  launched: boolean
  detail?: string | null
  notify: boolean
}

export const launchApi = {
  terminal: (
    provider: CliProvider,
    projectId?: string,
    workflowId?: string,
    instruction?: string,
    language?: 'en' | 'pt',
    referenceWorkflowIds?: string[],
  ) =>
    api.post<LaunchResult>('/api/launch/terminal', {
      provider,
      projectId,
      workflowId,
      instruction,
      language,
      referenceWorkflowIds,
    }),
  claudeDesktop: () => api.post<LaunchResult>('/api/launch/claude-desktop', {}),
}
