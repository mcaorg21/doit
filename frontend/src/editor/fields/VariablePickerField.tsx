import { useState } from 'react'
import { ApiError } from '../../api/client'
import type { VariableSource } from '../graph'
import type { ParamFieldSpec } from '../../types/nodeType'

interface Props {
  spec: ParamFieldSpec
  value: unknown
  onChange: (value: unknown) => void
  sources: VariableSource[]
  onPreview: (source: VariableSource) => Promise<unknown>
}

type PreviewState = { loading: boolean; value?: unknown; error?: string }

export default function VariablePickerField({ spec, value, onChange, sources, onPreview }: Props) {
  const [preview, setPreview] = useState<PreviewState | null>(null)

  async function handleSelect(variableName: string) {
    onChange(variableName)
    const source = sources.find((s) => s.variableName === variableName)
    if (!source) {
      setPreview(null)
      return
    }
    setPreview({ loading: true })
    try {
      const result = await onPreview(source)
      setPreview({ loading: false, value: result })
    } catch (err) {
      setPreview({ loading: false, error: err instanceof ApiError ? err.message : 'Failed to preview' })
    }
  }

  return (
    <div className="field">
      <label>
        {spec.label}
        {spec.required ? ' *' : ''}
      </label>
      <select value={(value as string) ?? ''} onChange={(e) => handleSelect(e.target.value)}>
        <option value="">Select a variable…</option>
        {sources.map((s) => (
          <option key={`${s.nodeId}.${s.paramKey}`} value={s.variableName}>
            {s.nodeLabel} → {s.variableName}
          </option>
        ))}
      </select>

      {sources.length === 0 && (
        <span className="hint">
          No earlier node in this chain defines a named variable yet (e.g. add an "Element Present?" node before
          this one).
        </span>
      )}
      {preview?.loading && <span className="hint">Running preview…</span>}
      {preview?.error && <div className="error-banner" style={{ margin: '6px 0 0' }}>{preview.error}</div>}
      {!preview?.loading && preview?.value !== undefined && (
        <pre
          style={{
            marginTop: 6,
            fontFamily: 'var(--mono)',
            fontSize: 12,
            background: 'var(--bg)',
            border: '1px solid var(--border)',
            padding: '6px 8px',
            borderRadius: 6,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}
        >
          {JSON.stringify(preview.value, null, 2)}
        </pre>
      )}
    </div>
  )
}
