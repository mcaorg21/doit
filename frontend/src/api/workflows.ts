import { api } from './client'
import type { RunRecord, WFEdge, WFNode, Workflow } from '../types/workflow'

export const workflowsApi = {
  list: (projectId: string) => api.get<Workflow[]>(`/api/projects/${projectId}/workflows`),
  create: (projectId: string, name: string, folderId: string | null = null) =>
    api.post<Workflow>(`/api/projects/${projectId}/workflows`, { name, folderId }),
  import: (
    projectId: string,
    name: string,
    nodes: WFNode[],
    edges: WFEdge[],
    folderId: string | null = null,
    startNodeId: string | null = null,
  ) => api.post<Workflow>(`/api/projects/${projectId}/workflows/import`, { name, nodes, edges, folderId, startNodeId }),
  get: (projectId: string, workflowId: string) =>
    api.get<Workflow>(`/api/projects/${projectId}/workflows/${workflowId}`),
  save: (
    projectId: string,
    workflowId: string,
    name: string,
    nodes: WFNode[],
    edges: WFEdge[],
    startNodeId: string | null = null,
  ) => api.put<Workflow>(`/api/projects/${projectId}/workflows/${workflowId}`, { name, nodes, edges, startNodeId }),
  remove: (projectId: string, workflowId: string) =>
    api.delete<void>(`/api/projects/${projectId}/workflows/${workflowId}`),
  duplicate: (projectId: string, workflowId: string) =>
    api.post<Workflow>(`/api/projects/${projectId}/workflows/${workflowId}/duplicate`),
  move: (projectId: string, workflowId: string, folderId: string | null) =>
    api.post<Workflow>(`/api/projects/${projectId}/workflows/${workflowId}/move`, { folderId }),
  publish: (projectId: string, workflowId: string) =>
    api.post<Workflow>(`/api/projects/${projectId}/workflows/${workflowId}/publish`),
  unpublish: (projectId: string, workflowId: string) =>
    api.post<Workflow>(`/api/projects/${projectId}/workflows/${workflowId}/unpublish`),
  getNotes: (projectId: string, workflowId: string) =>
    api.get<{ notes: string }>(`/api/projects/${projectId}/workflows/${workflowId}/notes`),
  setNotes: (projectId: string, workflowId: string, notes: string) =>
    api.put<{ notes: string }>(`/api/projects/${projectId}/workflows/${workflowId}/notes`, { notes }),
  generateCode: (
    projectId: string,
    workflowId: string,
    nodes: WFNode[],
    edges: WFEdge[],
    startNodeId: string | null = null,
  ) =>
    api.post<{ code: string }>(`/api/projects/${projectId}/workflows/${workflowId}/generate-code`, {
      nodes,
      edges,
      startNodeId,
    }),
  run: (projectId: string, workflowId: string, nodes: WFNode[], edges: WFEdge[], startNodeId: string | null = null) =>
    api.post<{ runId: string }>(`/api/projects/${projectId}/workflows/${workflowId}/run`, {
      nodes,
      edges,
      startNodeId,
    }),
  listRuns: (projectId: string, workflowId?: string) =>
    api.get<RunRecord[]>(
      `/api/projects/${projectId}/runs${workflowId ? `?workflowId=${encodeURIComponent(workflowId)}` : ''}`,
    ),
  previewVariable: (
    projectId: string,
    workflowId: string,
    nodes: WFNode[],
    edges: WFEdge[],
    nodeId: string,
    variableName: string,
    startNodeId: string | null = null,
  ) =>
    api.post<{ value: unknown }>(`/api/projects/${projectId}/workflows/${workflowId}/preview-variable`, {
      nodes,
      edges,
      nodeId,
      variableName,
      startNodeId,
    }),
}
