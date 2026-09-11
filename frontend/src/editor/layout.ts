import type { Edge, Node } from '@xyflow/react'
import type { FlowEdgeData, FlowNodeData } from './types'

const START_X = 80
const START_Y = 80
const COLUMN_GAP = 190
const ROW_GAP = 130

/**
 * Lays a workflow out from left to right, following its connections. A straight
 * chain stays on one row, while branches and disconnected roots get their own
 * vertical space. Existing node data and selection are preserved.
 */
export function arrangeWorkflowNodes(
  nodes: Node<FlowNodeData>[],
  edges: Edge<FlowEdgeData>[],
  startNodeId: string | null,
): Node<FlowNodeData>[] {
  if (nodes.length === 0) return nodes

  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const incomingCount = new Map(nodes.map((node) => [node.id, 0]))
  const outgoing = new Map(nodes.map((node) => [node.id, [] as string[]]))

  for (const edge of edges) {
    if (!nodeById.has(edge.source) || !nodeById.has(edge.target)) continue
    outgoing.get(edge.source)!.push(edge.target)
    incomingCount.set(edge.target, (incomingCount.get(edge.target) ?? 0) + 1)
  }

  // Keep branch placement deterministic: true above false, then retain the
  // canvas' current vertical order for ordinary or malformed multi-edges.
  for (const [source, targets] of outgoing) {
    targets.sort((a, b) => {
      const edgeA = edges.find((edge) => edge.source === source && edge.target === a)
      const edgeB = edges.find((edge) => edge.source === source && edge.target === b)
      const handleRank = (handle: string | null | undefined) => (handle === 'true' ? 0 : handle === 'false' ? 1 : 2)
      return handleRank(edgeA?.sourceHandle) - handleRank(edgeB?.sourceHandle) ||
        nodeById.get(a)!.position.y - nodeById.get(b)!.position.y
    })
  }

  const roots = nodes
    .filter((node) => (incomingCount.get(node.id) ?? 0) === 0)
    .sort((a, b) => {
      if (a.id === startNodeId) return -1
      if (b.id === startNodeId) return 1
      return a.position.y - b.position.y || a.position.x - b.position.x
    })

  const positions = new Map<string, { x: number; y: number }>()
  const visited = new Set<string>()
  let nextRow = 0

  const place = (nodeId: string, depth: number, path: Set<string>): number => {
    const existing = positions.get(nodeId)
    if (existing) return existing.y
    if (path.has(nodeId)) {
      const y = START_Y + nextRow++ * ROW_GAP
      positions.set(nodeId, { x: START_X + depth * COLUMN_GAP, y })
      return y
    }

    visited.add(nodeId)
    const nextPath = new Set(path).add(nodeId)
    const children = (outgoing.get(nodeId) ?? []).filter((id) => !positions.has(id))
    let y: number
    if (children.length === 0) {
      y = START_Y + nextRow++ * ROW_GAP
    } else {
      const childRows = children.map((childId) => place(childId, depth + 1, nextPath))
      y = childRows.reduce((sum, childY) => sum + childY, 0) / childRows.length
    }
    positions.set(nodeId, { x: START_X + depth * COLUMN_GAP, y })
    return y
  }

  for (const root of roots) place(root.id, 0, new Set())
  // Invalid/cyclic or otherwise unreachable fragments should still be made visible.
  for (const node of nodes) {
    if (!visited.has(node.id)) place(node.id, 0, new Set())
  }

  return nodes.map((node) => ({ ...node, position: positions.get(node.id) ?? node.position }))
}
