import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { FlowNodeData } from '../types'
import NodeIcon from './icons'

interface Props extends NodeProps {
  data: FlowNodeData
  onDelete: (nodeId: string) => void
}

const SQUARE_SIZE = 56

export default function GenericNode({ id, data, selected, onDelete }: Props) {
  const heading = data.title?.trim() || data.label

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
        style={{
          width: SQUARE_SIZE,
          height: SQUARE_SIZE,
          border: `1px solid ${selected ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: 12,
          background: 'var(--surface)',
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text)',
          boxShadow: selected ? '0 0 0 2px var(--accent-bg)' : undefined,
        }}
      >
        <Handle type="target" position={Position.Top} />

        <button
          className="node-delete-btn"
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

        <NodeIcon name={data.icon} size={26} />

        {data.isBranch ? (
          <>
            <Handle type="source" id="true" position={Position.Bottom} style={{ left: '25%' }} />
            <span
              style={{
                position: 'absolute',
                bottom: -16,
                left: '25%',
                transform: 'translateX(-50%)',
                fontSize: 9,
                color: 'var(--success)',
              }}
            >
              true
            </span>
            <Handle type="source" id="false" position={Position.Bottom} style={{ left: '75%' }} />
            <span
              style={{
                position: 'absolute',
                bottom: -16,
                left: '75%',
                transform: 'translateX(-50%)',
                fontSize: 9,
                color: 'var(--danger)',
              }}
            >
              false
            </span>
          </>
        ) : (
          <Handle type="source" position={Position.Bottom} />
        )}
      </div>

      <div
        style={{
          marginTop: data.isBranch ? 20 : 6,
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
    </div>
  )
}
