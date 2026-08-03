import { api } from './client'
import type { RunRecord, WFEdge, WFNode, Workflow } from '../types/workflow'

export const workflowsApi = {
  list: (projectId: string) => api.get<Workflow[]>(`/api/projects/${projectId}/workflows`),
  create: (projectId: string, name: string) =>
    api.post<Workflow>(`/api/projects/${projectId}/workflows`, { name }),
  get: (projectId: string, workflowId: string) =>
    api.get<Workflow>(`/api/projects/${projectId}/workflows/${workflowId}`),
  save: (projectId: string, workflowId: string, name: string, nodes: WFNode[], edges: WFEdge[]) =>
    api.put<Workflow>(`/api/projects/${projectId}/workflows/${workflowId}`, { name, nodes, edges }),
  remove: (projectId: string, workflowId: string) =>
    api.delete<void>(`/api/projects/${projectId}/workflows/${workflowId}`),
  generateCode: (projectId: string, workflowId: string, nodes: WFNode[], edges: WFEdge[]) =>
    api.post<{ code: string }>(`/api/projects/${projectId}/workflows/${workflowId}/generate-code`, {
      nodes,
      edges,
    }),
  run: (projectId: string, workflowId: string, nodes: WFNode[], edges: WFEdge[]) =>
    api.post<{ runId: string }>(`/api/projects/${projectId}/workflows/${workflowId}/run`, { nodes, edges }),
  listRuns: (projectId: string) => api.get<RunRecord[]>(`/api/projects/${projectId}/runs`),
}
