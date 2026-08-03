import type { ParamFieldSpec } from '../../types/nodeType'

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
      ) : (
        <input
          type="text"
          value={(value as string) ?? ''}
          placeholder={spec.placeholder ?? undefined}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
      {spec.supportsTemplate && <span className="hint">Supports {'{{item.field}}'}</span>}
    </div>
  )
}
