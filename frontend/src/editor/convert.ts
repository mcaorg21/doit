import type { Edge, Node } from '@xyflow/react'
import type { WFEdge, WFNode } from '../types/workflow'
import type { NodeTypeSpec } from '../types/nodeType'
import type { FlowEdgeData, FlowNodeData } from './types'

export function toWFNodes(nodes: Node<FlowNodeData>[]): WFNode[] {
  return nodes.map((n) => ({
    id: n.id,
    type: n.data.nodeType,
    position: { x: n.position.x, y: n.position.y },
    params: n.data.params,
    title: n.data.title,
    note: n.data.note,
    fieldMap: n.data.fieldMap,
    resultExamples: n.data.resultExamples,
    resultTypes: n.data.resultTypes,
    maxAttempts: n.data.maxAttempts,
    retryDelaySeconds: n.data.retryDelaySeconds,
  }))
}

export function toWFEdges(edges: Edge<FlowEdgeData>[]): WFEdge[] {
  return edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle,
    breakpoint: e.data?.breakpoint ?? false,
  }))
}

// The reverse direction — used both by EditorPage's initial load and by the live
// events applied from /ws/workflows/{id} (a node/edge the MCP server just created).
// NOTE: unlike the initial-load effect, this does NOT backfill empty autoGenerate
// fields (e.g. Webhook's Secret) — a node created remotely with one unset stays
// unset until the workflow is reloaded. Not expected to matter for the node types
// the MCP live-build tools actually create today, but worth knowing if that changes.
export function wfNodeToFlowNode(n: WFNode, nodeTypesByType: Map<string, NodeTypeSpec>): Node<FlowNodeData> {
  const spec = nodeTypesByType.get(n.type)
  return {
    id: n.id,
    type: 'generic',
    position: n.position,
    data: {
      nodeType: n.type,
      label: spec?.label ?? n.type,
      params: n.params,
      isBranch: spec?.isBranch ?? false,
      icon: spec?.icon ?? null,
      title: n.title ?? undefined,
      note: n.note ?? undefined,
      fieldMap: n.fieldMap ?? undefined,
      resultExamples: n.resultExamples ?? undefined,
      resultTypes: n.resultTypes ?? undefined,
      maxAttempts: n.maxAttempts ?? undefined,
      retryDelaySeconds: n.retryDelaySeconds ?? undefined,
    },
  }
}

export function wfEdgeToFlowEdge(e: WFEdge): Edge<FlowEdgeData> {
  return {
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle ?? undefined,
    type: 'breakpoint',
    data: { breakpoint: e.breakpoint ?? false },
  }
}
