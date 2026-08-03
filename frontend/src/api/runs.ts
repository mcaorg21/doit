import { api } from './client'

export const runsApi = {
  continue_: (runId: string) => api.post<{ ok: boolean }>(`/api/runs/${runId}/continue`),
  sendInput: (runId: string, text: string) => api.post<{ ok: boolean }>(`/api/runs/${runId}/input`, { text }),
  stop: (runId: string) => api.post<{ ok: boolean }>(`/api/runs/${runId}/stop`),
}
