import type { Edge, Node } from '@xyflow/react'
import type { FlowEdgeData, FlowNodeData } from './types'
import type { NodeTypeSpec } from '../types/nodeType'

/** Walks backward from nodeId via edges (target -> source) to the root, in order
 * from nearest ancestor to furthest — matches the engine's <=1-incoming-edge rule. */
export function getUpstreamNodes(
  nodeId: string,
  nodes: Node<FlowNodeData>[],
  edges: Edge<FlowEdgeData>[],
): Node<FlowNodeData>[] {
  const nodeById = new Map(nodes.map((n) => [n.id, n]))
  const sourceByTarget = new Map(edges.map((e) => [e.target, e.source]))

  const result: Node<FlowNodeData>[] = []
  const seen = new Set<string>([nodeId])
  let current = sourceByTarget.get(nodeId)
  while (current && !seen.has(current)) {
    seen.add(current)
    const node = nodeById.get(current)
    if (node) result.push(node)
    current = sourceByTarget.get(current)
  }
  return result
}

export interface VariableSource {
  nodeId: string
  nodeLabel: string
  paramKey: string
  variableName: string
}

/** Upstream nodes' fields marked producesVariable, with the variable name the user
 * actually typed in for that node instance (skipped if left blank). */
export function getUpstreamVariables(
  nodeId: string,
  nodes: Node<FlowNodeData>[],
  edges: Edge<FlowEdgeData>[],
  nodeTypesByType: Map<string, NodeTypeSpec>,
): VariableSource[] {
  const sources: VariableSource[] = []
  for (const node of getUpstreamNodes(nodeId, nodes, edges)) {
    const spec = nodeTypesByType.get(node.data.nodeType)
    if (!spec) continue
    for (const p of spec.params) {
      if (!p.producesVariable) continue
      const value = node.data.params[p.key]
      if (typeof value === 'string' && value.trim()) {
        sources.push({
          nodeId: node.id,
          nodeLabel: node.data.title?.trim() || node.data.label,
          paramKey: p.key,
          variableName: value.trim(),
        })
      }
    }
  }
  return sources
}
