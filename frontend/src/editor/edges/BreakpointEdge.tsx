import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from '@xyflow/react'
import type { FlowEdgeData } from '../types'

interface Props extends EdgeProps {
  data?: FlowEdgeData
  onToggle: (edgeId: string) => void
  onDelete: (edgeId: string) => void
}

export default function BreakpointEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  style,
  data,
  onToggle,
  onDelete,
}: Props) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })
  const active = Boolean(data?.breakpoint)

  return (
    <>
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} style={style} />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            pointerEvents: 'all',
          }}
        >
          <button
            onClick={(e) => {
              e.stopPropagation()
              onToggle(id)
            }}
            title={active ? 'Breakpoint active — click to remove' : 'Click to add a breakpoint here'}
            style={{
              width: 16,
              height: 16,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: '50%',
              border: active ? '2px solid var(--danger)' : '1px solid var(--border)',
              background: active ? 'var(--danger)' : 'var(--surface)',
              boxShadow: active ? '0 0 0 3px rgba(220, 38, 38, 0.25)' : undefined,
              padding: 0,
              cursor: 'pointer',
            }}
          >
            <svg
              width="7"
              height="7"
              viewBox="0 0 24 24"
              fill={active ? '#fff' : 'var(--text-muted)'}
              style={{ opacity: active ? 1 : 0.5 }}
            >
              <rect x="5" y="3" width="5" height="18" rx="1" />
              <rect x="14" y="3" width="5" height="18" rx="1" />
            </svg>
          </button>

          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete(id)
            }}
            title="Delete connection"
            style={{
              width: 16,
              height: 16,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: '50%',
              border: '1px solid var(--border)',
              background: 'var(--surface)',
              color: 'var(--text-muted)',
              padding: 0,
              cursor: 'pointer',
              opacity: 0.7,
            }}
          >
            <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              <line x1="10" y1="11" x2="10" y2="17" />
              <line x1="14" y1="11" x2="14" y2="17" />
            </svg>
          </button>
        </div>
      </EdgeLabelRenderer>
    </>
  )
}
