import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { workflowsApi } from '../api/workflows'
import type { RunStatus } from '../types/workflow'

interface Props {
  projectId: string
  /** Omit to show every run in the project (project-level report); pass a workflow
   * id to filter to just that workflow's runs (used by the editor's Executions tab). */
  workflowId?: string
  /** Only relevant at project level, where each row needs to say which workflow ran —
   * maps workflowId -> display name so we don't have to guess from the id. */
  workflowNames?: Map<string, string>
}

const STATUS_LABELS: Record<RunStatus, string> = {
  running: 'Running…',
  success: 'Success',
  error: 'Error',
  cancelled: 'Cancelled',
}

function formatDuration(startedAt: string, finishedAt: string | null): string {
  if (!finishedAt) return '—'
  const ms = new Date(finishedAt).getTime() - new Date(startedAt).getTime()
  if (ms < 1000) return `${ms}ms`
  const totalSeconds = ms / 1000
  if (totalSeconds < 60) return `${totalSeconds.toFixed(1)}s`
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = Math.round(totalSeconds % 60)
  return `${minutes}m ${seconds}s`
}

const PAGE_SIZE = 20

export default function ExecutionsPanel({ projectId, workflowId, workflowNames }: Props) {
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null)
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)

  const { data: runs, isLoading } = useQuery({
    queryKey: ['runs', projectId, workflowId ?? 'all'],
    queryFn: () => workflowsApi.listRuns(projectId, workflowId),
    // Runs list changes outside user interaction too (scheduled/webhook triggers) —
    // a light poll keeps this report current without needing a websocket for it.
    refetchInterval: 5000,
  })

  if (isLoading) return <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading…</p>

  if (!runs || runs.length === 0) {
    return <div className="empty-state">No executions yet.</div>
  }

  const visibleRuns = runs.slice(0, visibleCount)

  return (
    <div className="list">
      {visibleRuns.map((run) => (
        <div key={run.id}>
          <div className="list-item" style={{ cursor: 'pointer' }} onClick={() => setExpandedRunId((cur) => (cur === run.id ? null : run.id))}>
            <div>
              <div className="list-item-title">
                {workflowNames && `${workflowNames.get(run.workflowId) ?? run.workflowId} — `}
                {new Date(run.startedAt).toLocaleString()}
              </div>
              <div className="list-item-meta">
                Duration: {formatDuration(run.startedAt, run.finishedAt)}
                {run.exitCode !== null && <> · Exit code: {run.exitCode}</>}
              </div>
            </div>
            <span className={`run-status ${run.status}`} style={{ margin: 0 }}>
              {STATUS_LABELS[run.status]}
            </span>
          </div>
          {expandedRunId === run.id && (
            <div
              style={{
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: 10,
                margin: '4px 0 10px',
                maxHeight: 300,
                overflow: 'auto',
                fontFamily: 'var(--mono)',
                fontSize: 12,
              }}
            >
              {run.logLines.length === 0 && <span style={{ color: 'var(--text-muted)' }}>No log output.</span>}
              {run.logLines.map((line, i) => (
                <div key={i} className={`log-line ${line.level === 'error' ? 'error' : ''}`}>
                  {line.text}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
      {runs.length > visibleCount && (
        <button className="btn btn-sm" style={{ margin: '4px 0' }} onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}>
          Ver mais ({runs.length - visibleCount} restantes)
        </button>
      )}
    </div>
  )
}
