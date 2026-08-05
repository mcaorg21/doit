export interface Project {
  id: string
  name: string
  createdAt: string
  updatedAt: string
}

export interface Position {
  x: number
  y: number
}

export interface WFNode {
  id: string
  type: string
  position: Position
  params: Record<string, unknown>
  title?: string | null
  note?: string | null
  fieldMap?: string[] | null
}

export interface WFEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string | null
  breakpoint?: boolean
}

export interface Workflow {
  id: string
  projectId: string
  name: string
  createdAt: string
  updatedAt: string
  nodes: WFNode[]
  edges: WFEdge[]
  published: boolean
  folderId: string | null
}

export interface Folder {
  id: string
  projectId: string
  name: string
  parentId: string | null
  createdAt: string
  updatedAt: string
}

export interface RunLogLine {
  ts: string
  level: string
  text: string
}

export type RunStatus = 'running' | 'success' | 'error' | 'cancelled'

export interface RunRecord {
  id: string
  workflowId: string
  startedAt: string
  finishedAt: string | null
  status: RunStatus
  exitCode: number | null
  scriptPath: string
  logLines: RunLogLine[]
}
