import { api } from './client'
import type { NodeTypeSpec } from '../types/nodeType'

export const nodeTypesApi = {
  list: () => api.get<NodeTypeSpec[]>('/api/node-types'),
}
