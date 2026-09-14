export interface FlowNodeData {
  nodeType: string
  label: string
  params: Record<string, unknown>
  isBranch?: boolean
  icon?: string | null
  title?: string
  note?: string
  isExecuting?: boolean
  hasExecutionError?: boolean
  isPaused?: boolean
  fieldMap?: string[]
  resultExamples?: Record<string, unknown>
  resultTypes?: Record<string, string>
  [key: string]: unknown
}

export interface FlowEdgeData {
  breakpoint?: boolean
  [key: string]: unknown
}
