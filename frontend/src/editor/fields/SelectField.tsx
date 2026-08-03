import type { FieldProps } from './TextField'

export default function SelectField({ spec, value, onChange }: FieldProps) {
  return (
    <div className="field">
      <label>
        {spec.label}
        {spec.required ? ' *' : ''}
      </label>
      <select value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)}>
        {(spec.options ?? []).map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}
