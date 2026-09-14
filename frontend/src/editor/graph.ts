import type { Edge, Node } from '@xyflow/react'
import type { FlowEdgeData, FlowNodeData } from './types'
import type { NodeTypeSpec } from '../types/nodeType'
import { flattenJsonPaths, referencePrefix } from './jsonPaths'

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

export interface FieldMapOption {
  nodeLabel: string
  path: string
  expr: string
}

/** Upstream nodes' saved field mappings (see GenericNode's "Save Mapping" button),
 * turned into ready-to-insert {{prefix.path}} expressions — the prefix is derived
 * from each source node's *current* params, so it stays correct even if the user
 * changes "Loop automatically" or renames the Result Variable after saving.
 *
 * Falls back to flattening a producesVariable field's captured example (see
 * backend/app/execution/runner.py's result capture) when there's no saved fieldMap
 * yet, so object-path suggestions show up the first time a downstream node is
 * configured — no need to open the source node and click "Save Mapping" first.
 * Skipped for a field explicitly declared "string" (see NodeConfigPanel's Result
 * Type control) — flattening a plain string's characters would be nonsense. */
export function getUpstreamFieldMapOptions(
  nodeId: string,
  nodes: Node<FlowNodeData>[],
  edges: Edge<FlowEdgeData>[],
  nodeTypesByType?: Map<string, NodeTypeSpec>,
): FieldMapOption[] {
  const options: FieldMapOption[] = []
  for (const node of getUpstreamNodes(nodeId, nodes, edges)) {
    const nodeLabel = node.data.title?.trim() || node.data.label
    const fieldMap = node.data.fieldMap
    if (fieldMap && fieldMap.length > 0) {
      const prefix = referencePrefix(node.data.params)
      for (const path of fieldMap) {
        options.push({ nodeLabel, path, expr: `{{${prefix}.${path}}}` })
      }
      continue
    }

    const spec = nodeTypesByType?.get(node.data.nodeType)
    if (!spec) continue
    for (const p of spec.params) {
      if (!p.producesVariable) continue
      const resultType = node.data.resultTypes?.[p.key] ?? 'auto'
      if (resultType === 'string') continue
      const example = node.data.resultExamples?.[p.key]
      if (example === undefined) continue
      if (resultType === 'auto' && (example === null || typeof example !== 'object')) continue
      const varName = typeof node.data.params[p.key] === 'string' ? (node.data.params[p.key] as string).trim() : ''
      if (!varName) continue
      // Same "item" vs resultVar-name convention the Save Mapping flow already
      // uses (see referencePrefix's own doc comment) — keeps a node's suggestions
      // consistent regardless of whether they came from a saved mapping or this
      // captured-example fallback.
      const prefix = referencePrefix(node.data.params)
      for (const path of flattenJsonPaths(example)) {
        options.push({ nodeLabel, path, expr: `{{${prefix}.${path}}}` })
      }
    }
  }
  return options
}
