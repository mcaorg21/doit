import { useRef, useState } from 'react'
import type { Edge, Node } from '@xyflow/react'
import { workflowsApi } from '../api/workflows'
import { runsApi } from '../api/runs'
import { toWFEdges, toWFNodes } from './convert'
import type { FlowEdgeData, FlowNodeData } from './types'
import { ApiError } from '../api/client'
import type { RunStatus } from '../types/workflow'

interface Props {
  projectId: string
  workflowId: string
  nodes: Node<FlowNodeData>[]
  edges: Edge<FlowEdgeData>[]
}

interface LogEntry {
  text: string
  level: string
}

const STATUS_LABELS: Record<RunStatus, string> = {
  running: 'Running…',
  success: '✓ Finished successfully',
  error: '✗ Run failed',
  cancelled: '⏹ Stopped',
}

export default function RunPanel({ projectId, workflowId, nodes, edges }: Props) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [status, setStatus] = useState<RunStatus | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pdbCommand, setPdbCommand] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const runIdRef = useRef<string | null>(null)

  const hasBreakpoints = edges.some((e) => e.data?.breakpoint)

  async function handleRun() {
    setLogs([])
    setStatus(null)
    setError(null)
    setRunning(true)
    runIdRef.current = null

    try {
      const { runId } = await workflowsApi.run(projectId, workflowId, toWFNodes(nodes), toWFEdges(edges))
      runIdRef.current = runId
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/runs/${runId}`)
      wsRef.current = ws

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)
        if (msg.type === 'log') {
          setLogs((prev) => [...prev, { text: msg.text, level: msg.level }])
        } else if (msg.type === 'done') {
          setStatus(msg.status)
          setRunning(false)
          ws.close()
        } else if (msg.type === 'error') {
          setError(msg.detail)
          setRunning(false)
          ws.close()
        }
      }
      ws.onerror = () => {
        setError('WebSocket connection error')
        setRunning(false)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to start run')
      setRunning(false)
    }
  }

  async function handleContinue() {
    if (!runIdRef.current) return
    try {
      await runsApi.continue_(runIdRef.current)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send continue')
    }
  }

  async function handleSendPdbCommand() {
    if (!runIdRef.current || !pdbCommand.trim()) return
    try {
      await runsApi.sendInput(runIdRef.current, pdbCommand)
      setPdbCommand('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send command')
    }
  }

  async function handleStop() {
    if (!runIdRef.current) return
    try {
      await runsApi.stop(runIdRef.current)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to stop run')
    }
  }

  function handleLogAreaKeyDown(e: React.KeyboardEvent) {
    const isCtrlC = (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c'
    if (!isCtrlC || !running) return
    // If the user has text selected, let the browser copy it as usual — only treat
    // Ctrl+C as "stop" when there's nothing to copy, like a real terminal would.
    const hasSelection = (window.getSelection()?.toString().length ?? 0) > 0
    if (hasSelection) return
    e.preventDefault()
    handleStop()
  }

  return (
    <div tabIndex={0} onKeyDown={handleLogAreaKeyDown} style={{ outline: 'none' }}>
      <button className="btn btn-primary btn-sm" onClick={handleRun} disabled={running || nodes.length === 0}>
        {running ? 'Running…' : '▶ Run'}
      </button>
      {running && (
        <button className="btn btn-sm" onClick={handleStop} style={{ marginLeft: 8 }} title="Stop (Ctrl+C)">
          ⏹ Stop
        </button>
      )}
      {hasBreakpoints && running && (
        <button className="btn btn-sm" onClick={handleContinue} style={{ marginLeft: 8 }}>
          ⏵ Continue past breakpoint
        </button>
      )}

      {running && (
        <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 6 }}>
          Click into this panel and press Ctrl+C to stop execution (when nothing is selected).
          {hasBreakpoints &&
            ' This workflow also has a breakpoint — if the log stops advancing, it\'s likely paused; click "Continue", or type a pdb command below (n, s, p <expr>, l, c, ...).'}
        </div>
      )}

      {hasBreakpoints && running && (
        <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
          <input
            value={pdbCommand}
            onChange={(e) => setPdbCommand(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSendPdbCommand()
            }}
            placeholder="pdb command, e.g. p item"
            style={{
              flex: 1,
              fontFamily: 'var(--mono)',
              fontSize: 13,
              padding: '6px 8px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              background: 'var(--bg)',
              color: 'var(--text)',
            }}
          />
          <button className="btn btn-sm" onClick={handleSendPdbCommand}>
            Send
          </button>
        </div>
      )}

      {status && <div className={`run-status ${status}`}>{STATUS_LABELS[status]}</div>}
      {error && <div className="error-banner">{error}</div>}

      <div style={{ marginTop: 8 }}>
        {logs.map((log, i) => (
          <div key={i} className={`log-line ${log.level === 'error' ? 'error' : ''}`}>
            {log.text}
          </div>
        ))}
      </div>
    </div>
  )
}
