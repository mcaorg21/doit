import { api } from './client'
import type { WFEdge, WFNode } from '../types/workflow'

export interface ReconstructPythonResult {
  name: string
  nodes: WFNode[]
  edges: WFEdge[]
  warnings: string[]
  unknownCount: number
}

export const llmImportApi = {
  reconstruct: (projectId: string, code: string, credentialId: string) =>
    api.post<ReconstructPythonResult>(`/api/projects/${projectId}/workflows/import-python/reconstruct`, {
      code,
      credentialId,
    }),
}
