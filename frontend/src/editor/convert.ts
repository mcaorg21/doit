import type { Edge, Node } from '@xyflow/react'
import type { WFEdge, WFNode } from '../types/workflow'
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
