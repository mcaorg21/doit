import type { FieldProps } from './TextField'

interface KeyValueRow {
  key: string
  value: string
}

function emptyRow(): KeyValueRow {
  return { key: '', value: '' }
}

// Renders a repeatable list of {key, value} rows, stored directly as an array in the
// param's value (same round-trip-with-no-extra-encoding trick as FieldListField) —
// used by HTTP Request for Headers and for its key/value Body Fields mode. Values
// support {{item.field}} / {{varName.field}} templates, same as a plain text field.
export default function KeyValueListField({ spec, value, onChange }: FieldProps) {
  const rows: KeyValueRow[] = Array.isArray(value) ? (value as KeyValueRow[]) : []

  function updateRow(index: number, patch: Partial<KeyValueRow>) {
    onChange(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)))
  }
  function addRow() {
    onChange([...rows, emptyRow()])
  }
  function removeRow(index: number) {
    onChange(rows.filter((_, i) => i !== index))
  }

  return (
    <div className="field">
      <label>{spec.label}</label>
      {rows.length === 0 && <span className="hint">None yet — add one below.</span>}

      {rows.map((row, i) => (
        <div key={i} className="field-list-row">
          <div className="field-list-row-pair">
            <input
              placeholder="Key, e.g. Authorization"
              value={row.key}
              onChange={(e) => updateRow(i, { key: e.target.value })}
            />
            <input
              placeholder="Value, e.g. Bearer {{item.token}}"
              value={row.value}
              onChange={(e) => updateRow(i, { value: e.target.value })}
            />
            <button
              type="button"
              className="icon-btn icon-btn-danger"
              title="Remove"
              onClick={() => removeRow(i)}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                <line x1="10" y1="11" x2="10" y2="17" />
                <line x1="14" y1="11" x2="14" y2="17" />
              </svg>
            </button>
          </div>
        </div>
      ))}

      <button type="button" className="btn btn-sm" onClick={addRow} style={{ marginTop: rows.length ? 8 : 4 }}>
        + Add
      </button>
      <span className="hint">
        Values support {'{{item.field}}'} inside a loop, or {'{{varName.field}}'} for a variable set by an earlier
        node.
      </span>
    </div>
  )
}
