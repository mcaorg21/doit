export interface Project {
  id: string
  name: string
  createdAt: string
  updatedAt: string
  workflowCount?: number
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
  resultExamples?: Record<string, unknown>
  resultTypes?: Record<string, string>
  maxAttempts?: number
  retryDelaySeconds?: number
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
  hasError: boolean
  folderId: string | null
  startNodeId?: string | null
}

export interface Folder {
  id: string
  projectId: string
  name: string
  parentId: string | null
  createdAt: string
  updatedAt: string
}

export interface Credential {
  id: string
  projectId: string
  name: string
  type: string
  value: string
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

export interface BackupCounts {
  projects: number
  folders: number
  workflows: number
  credentials: number
  runs: number
}

export interface BackupStatus {
  configured: boolean
  connectionString?: string | null
  lastBackupAt?: string | null
  lastBackupCounts?: BackupCounts | null
  lastRestoreAt?: string | null
}

export interface BackupResult {
  counts: BackupCounts
  warnings: string[]
  finishedAt: string
}

export interface RestorePreview {
  counts: BackupCounts
  lastUpdatedAt: Record<string, string | null>
}

export interface RestoreResult {
  counts: BackupCounts
  finishedAt: string
}
