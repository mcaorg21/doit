import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { ApiError } from '../../api/client'
import type { FlowNodeData } from '../types'
import NodeIcon from './icons'

interface Props extends NodeProps {
  data: FlowNodeData
  onDelete: (nodeId: string) => void
  onDuplicate: (nodeId: string) => void
  onRunPreview?: (nodeId: string) => Promise<unknown>
}

const SQUARE_SIZE = 56

type PreviewState = { loading: boolean; value?: unknown; error?: string }

export default function GenericNode({ id, data, selected, onDelete, onDuplicate, onRunPreview }: Props) {
  const [preview, setPreview] = useState<PreviewState | null>(null)
  const heading = data.title?.trim() || data.label

  async function handleRun(e: React.MouseEvent) {
    e.stopPropagation()
    if (!onRunPreview) return
    setPreview({ loading: true })
    try {
      const value = await onRunPreview(id)
      setPreview({ loading: false, value })
    } catch (err) {
      setPreview({
        loading: false,
        error: err instanceof ApiError || err instanceof Error ? err.message : 'Failed to run',
      })
    }
  }

  const summary = Object.entries(data.params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .slice(0, 3)
    .map(([k, v]) => `${k}: ${String(v)}`)
    .join('\n')
  const tooltip = [data.note, summary].filter(Boolean).join('\n\n') || undefined

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 84 }}>
      <div
        title={tooltip}
        className={data.isExecuting ? 'node-executing' : undefined}
        style={{
          width: SQUARE_SIZE,
          height: SQUARE_SIZE,
          border: `1px solid ${data.isExecuting ? 'var(--success)' : selected ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: 12,
          background: 'var(--surface)',
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text)',
          boxShadow: data.isExecuting ? undefined : selected ? '0 0 0 2px var(--accent-bg)' : undefined,
        }}
      >
        <Handle type="target" position={Position.Left} />

        <div className="node-toolbar">
          {data.nodeType === 'http_request' && onRunPreview && (
            <button className="node-toolbar-btn" onClick={handleRun} title="Run this node and preview the result">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="6 3 20 12 6 21 6 3" />
              </svg>
            </button>
          )}
          <button
            className="node-toolbar-btn"
            onClick={(e) => {
              e.stopPropagation()
              onDuplicate(id)
            }}
            title="Duplicate node"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          </button>
          <button
            className="node-toolbar-btn"
            onClick={(e) => {
              e.stopPropagation()
              onDelete(id)
            }}
            title="Delete node"
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              <line x1="10" y1="11" x2="10" y2="17" />
              <line x1="14" y1="11" x2="14" y2="17" />
            </svg>
          </button>
        </div>

        <NodeIcon name={data.icon} size={26} />

        {data.isBranch ? (
          <>
            <Handle type="source" id="true" position={Position.Right} style={{ top: '25%' }} />
            <span
              style={{
                position: 'absolute',
                right: -24,
                top: '25%',
                transform: 'translateY(-50%)',
                fontSize: 9,
                color: 'var(--success)',
              }}
            >
              true
            </span>
            <Handle type="source" id="false" position={Position.Right} style={{ top: '75%' }} />
            <span
              style={{
                position: 'absolute',
                right: -28,
                top: '75%',
                transform: 'translateY(-50%)',
                fontSize: 9,
                color: 'var(--danger)',
              }}
            >
              false
            </span>
          </>
        ) : (
          <Handle type="source" position={Position.Right} />
        )}
      </div>

      <div
        style={{
          marginTop: 6,
          fontSize: 11,
          fontWeight: 600,
          textAlign: 'center',
          lineHeight: 1.3,
          wordBreak: 'break-word',
        }}
      >
        {heading}
      </div>
      {data.title?.trim() && (
        <div style={{ color: 'var(--text-muted)', fontSize: 9, marginTop: 1 }}>{data.label}</div>
      )}

      {preview &&
        createPortal(
          // Rendered via a portal straight onto <body> — this node lives inside React
          // Flow's pan/zoom pane, which has a CSS transform on it; a `position: fixed`
          // element nested inside a transformed ancestor is positioned/scaled relative
          // to THAT ancestor instead of the real viewport (a CSS spec quirk), which is
          // why this must escape the React Flow tree entirely rather than just being
          // absolutely positioned within it.
          <div className="modal-overlay" onClick={() => setPreview(null)}>
            <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 480 }}>
              <h3>Result — {heading}</h3>
              {preview.loading && <span className="hint">Running…</span>}
              {preview.error && <div className="error-banner">{preview.error}</div>}
              {!preview.loading && preview.value !== undefined && (
                <pre
                  style={{
                    margin: 0,
                    fontFamily: 'var(--mono)',
                    fontSize: 12,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    padding: '8px 10px',
                    maxHeight: '60vh',
                    overflow: 'auto',
                  }}
                >
                  {JSON.stringify(preview.value, null, 2)}
                </pre>
              )}
              <div className="modal-actions">
                <button className="btn btn-primary" onClick={() => setPreview(null)}>
                  Close
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </div>
  )
}
