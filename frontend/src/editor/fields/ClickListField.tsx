import type { FieldProps } from './TextField'

interface ClickRow {
  selector: string
  selectorType: string
}

const SELECTOR_TYPE_OPTIONS = [
  { value: 'css', label: 'CSS Selector' },
  { value: 'id', label: 'ID' },
  { value: 'class_name', label: 'Class Name' },
  { value: 'xpath', label: 'XPath' },
  { value: 'full_xpath', label: 'Full XPath' },
]

function emptyRow(): ClickRow {
  return { selector: '', selectorType: 'css' }
}

// Renders a repeatable list of {selector, selectorType} rows, stored directly as an
// array in the param's value (same round-trip-with-no-extra-encoding trick as
// FieldListField) — used by Multi Click to click several elements in one step.
export default function ClickListField({ spec, value, onChange }: FieldProps) {
  const rows: ClickRow[] = Array.isArray(value) ? (value as ClickRow[]) : []

  function updateRow(index: number, patch: Partial<ClickRow>) {
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
      {rows.length === 0 && <span className="hint">No clicks yet — add one below.</span>}

      {rows.map((row, i) => (
        <div key={i} className="field-list-row">
          <div className="field-list-row-header">
            <strong>Click {i + 1}</strong>
            <button
              type="button"
              className="icon-btn icon-btn-danger"
              title="Remove click"
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
          <input
            placeholder="Selector value, e.g. button[type=submit]"
            value={row.selector}
            onChange={(e) => updateRow(i, { selector: e.target.value })}
          />
          <select value={row.selectorType} onChange={(e) => updateRow(i, { selectorType: e.target.value })}>
            {SELECTOR_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      ))}

      <button type="button" className="btn btn-sm" onClick={addRow} style={{ marginTop: rows.length ? 8 : 4 }}>
        + Add Click
      </button>
    </div>
  )
}
