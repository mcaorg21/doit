export interface FlowNodeData {
  nodeType: string
  label: string
  params: Record<string, unknown>
  isBranch?: boolean
  icon?: string | null
  title?: string
  note?: string
  [key: string]: unknown
}

export interface FlowEdgeData {
  breakpoint?: boolean
  [key: string]: unknown
}
