import type { ParamFieldSpec } from '../../types/nodeType'
import { genRandomToken } from '../randomToken'

export interface FieldProps {
  spec: ParamFieldSpec
  value: unknown
  onChange: (value: unknown) => void
}

export default function TextField({ spec, value, onChange }: FieldProps) {
  return (
    <div className="field">
      <label>
        {spec.label}
        {spec.required ? ' *' : ''}
      </label>
      {spec.type === 'textarea' ? (
        <textarea
          value={(value as string) ?? ''}
          placeholder={spec.placeholder ?? undefined}
          rows={4}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : spec.autoGenerate ? (
        <div style={{ display: 'flex', gap: 6 }}>
          <input type="text" value={(value as string) ?? ''} readOnly style={{ flex: 1, fontFamily: 'var(--mono)' }} />
          <button type="button" className="btn btn-sm" title="Generate a new secret" onClick={() => onChange(genRandomToken())}>
            ↻
          </button>
        </div>
      ) : (
        <input
          type="text"
          value={(value as string) ?? ''}
          placeholder={spec.placeholder ?? undefined}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
      {spec.supportsTemplate && (
        <span className="hint">
          Supports {'{{item.field}}'} inside a loop, or {'{{varName.field}}'} for a variable set by an earlier node
          (e.g. HTTP Request's Result Variable) — nested fields work too, e.g. {'{{item.address.street}}'}
        </span>
      )}
    </div>
  )
}
