import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from '@xyflow/react'
import type { FlowEdgeData } from '../types'

interface Props extends EdgeProps {
  data?: FlowEdgeData
  onToggle: (edgeId: string) => void
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
        <button
          onClick={(e) => {
            e.stopPropagation()
            onToggle(id)
          }}
          title={active ? 'Breakpoint active — click to remove' : 'Click to add a breakpoint here'}
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
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
            pointerEvents: 'all',
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
      </EdgeLabelRenderer>
    </>
  )
}
