import type { FieldProps } from './TextField'

export default function NumberField({ spec, value, onChange }: FieldProps) {
  return (
    <div className="field">
      <label>
        {spec.label}
        {spec.required ? ' *' : ''}
      </label>
      <input
        type="number"
        value={(value as number) ?? ''}
        placeholder={spec.placeholder ?? undefined}
        onChange={(e) => onChange(e.target.valueAsNumber)}
      />
    </div>
  )
}
