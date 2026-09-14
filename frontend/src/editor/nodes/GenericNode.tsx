import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { ApiError } from '../../api/client'
import type { FlowNodeData } from '../types'
import { flattenJsonPaths, referencePrefix } from '../jsonPaths'
import JsonPathViewer from '../JsonPathViewer'
import NodeIcon from './icons'
import { useLanguage } from '../../i18n/LanguageContext'
import { nodeCatalogPt } from '../../i18n/nodeCatalog'

interface Props extends NodeProps {
  data: FlowNodeData
  isStartNode?: boolean
  onDelete: (nodeId: string) => void
  onDuplicate: (nodeId: string) => void
  onSetStartNode?: (nodeId: string) => void
  onRunPreview?: (nodeId: string) => Promise<unknown>
  onSaveFieldMap?: (nodeId: string, fieldMap: string[]) => void
}

const SQUARE_SIZE = 56

type PreviewState = { loading: boolean; value?: unknown; error?: string }

export default function GenericNode({
  id,
  data,
  selected,
  isStartNode,
  onDelete,
  onDuplicate,
  onSetStartNode,
  onRunPreview,
  onSaveFieldMap,
}: Props) {
  const [preview, setPreview] = useState<PreviewState | null>(null)
  const [mappingSaved, setMappingSaved] = useState(false)
  const { language } = useLanguage()
  // A custom title (set by a human or an AI-authored node) is always shown as-is —
  // only the DEFAULT label (the node type's own generic name, e.g. "Click") gets
  // the Portuguese catalog override, same display-layer-only translation as the
  // palette (see i18n/nodeCatalog.ts).
  const translatedLabel = language === 'pt' ? (nodeCatalogPt[data.nodeType]?.label ?? data.label) : data.label
  const heading = data.title?.trim() || translatedLabel

  async function handleRun(e: React.MouseEvent) {
    e.stopPropagation()
    if (!onRunPreview) return
    setPreview({ loading: true })
    setMappingSaved(false)
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
        title={data.isPaused ? [tooltip, 'Paused at a breakpoint — use Continue in the Run panel'].filter(Boolean).join('\n\n') : tooltip}
        className={data.isPaused ? 'node-paused' : data.isExecuting ? 'node-executing' : undefined}
        style={{
          width: SQUARE_SIZE,
          height: SQUARE_SIZE,
          border: `1px solid ${data.hasExecutionError || data.isPaused ? 'var(--danger)' : data.isExecuting ? 'var(--success)' : selected ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: 12,
          background: 'var(--surface)',
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text)',
          boxShadow:
            data.hasExecutionError && !data.isPaused
              ? '0 0 0 3px color-mix(in srgb, var(--danger) 30%, transparent)'
              : data.isExecuting || data.isPaused
                ? undefined
                : selected
                  ? '0 0 0 2px var(--accent-bg)'
                  : undefined,
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
          {onSetStartNode && (
            <button
              className="node-toolbar-btn"
              onClick={(e) => {
                e.stopPropagation()
                onSetStartNode(id)
              }}
              title={isStartNode ? 'Unset as Start Node' : 'Set as Start Node — used when the graph has more than one disconnected root'}
            >
              <svg
                width="10"
                height="10"
                viewBox="0 0 24 24"
                fill={isStartNode ? 'currentColor' : 'none'}
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={isStartNode ? { color: 'var(--success)' } : undefined}
              >
                <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
                <line x1="4" y1="22" x2="4" y2="4" />
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

        {isStartNode && (
          <span
            title="Start Node"
            style={{
              position: 'absolute',
              top: -6,
              left: -6,
              width: 15,
              height: 15,
              borderRadius: '50%',
              background: 'var(--success)',
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 0 2px var(--surface)',
            }}
          >
            <svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor" stroke="none">
              <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
            </svg>
          </span>
        )}

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
        <div style={{ color: 'var(--text-muted)', fontSize: 9, marginTop: 1 }}>{translatedLabel}</div>
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
                <>
                  <span className="hint">
                    Hover a value for its {'{{'}
                    {referencePrefix(data.params)}
                    {'.field}}'} reference, click to copy.
                  </span>
                  <div
                    style={{
                      background: 'var(--bg)',
                      border: '1px solid var(--border)',
                      borderRadius: 6,
                      padding: '8px 10px',
                      maxHeight: '60vh',
                      overflow: 'auto',
                    }}
                  >
                    <JsonPathViewer value={preview.value} prefix={referencePrefix(data.params)} />
                  </div>
                </>
              )}
              <div className="modal-actions">
                {!preview.loading && preview.value !== undefined && onSaveFieldMap && (
                  <button
                    className="btn"
                    onClick={() => {
                      onSaveFieldMap(id, flattenJsonPaths(preview.value))
                      setMappingSaved(true)
                    }}
                    title="Saves these field paths so other nodes' template-capable fields can suggest them"
                  >
                    {mappingSaved ? 'Mapping saved ✓' : 'Save Mapping'}
                  </button>
                )}
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
