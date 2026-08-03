import type { FieldProps } from './TextField'

export default function BooleanField({ spec, value, onChange }: FieldProps) {
  return (
    <div className="field">
      <label>
        <input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />{' '}
        {spec.label}
      </label>
    </div>
  )
}
