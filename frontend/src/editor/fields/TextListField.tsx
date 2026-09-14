import type { FieldProps } from './TextField'
import { useLanguage } from '../../i18n/LanguageContext'

// Renders a repeatable list of plain text strings, stored directly as a string[] in
// the param's value (same round-trip-with-no-extra-encoding trick as ClickListField/
// FieldListField) — simpler than those two since each row is just one bare string,
// no selector/selectorType pair. Used by HTML List Select's Checkbox mode (several
// option labels clicked in sequence).
export default function TextListField({ spec, value, onChange }: FieldProps) {
  const { t } = useLanguage()
  const rows: string[] = Array.isArray(value) ? (value as string[]) : []

  function updateRow(index: number, text: string) {
    onChange(rows.map((r, i) => (i === index ? text : r)))
  }
  function addRow() {
    onChange([...rows, ''])
  }
  function removeRow(index: number) {
    onChange(rows.filter((_, i) => i !== index))
  }

  return (
    <div className="field">
      <label>{spec.label}</label>
      {rows.length === 0 && <span className="hint">{t('noOptionsYetHint')}</span>}

      {rows.map((text, i) => (
        <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
          <input
            placeholder="Option text, e.g. Aprovado"
            value={text}
            onChange={(e) => updateRow(i, e.target.value)}
            style={{ flex: 1 }}
          />
          <button type="button" className="icon-btn icon-btn-danger" title={t('removeOptionTitle')} onClick={() => removeRow(i)}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              <line x1="10" y1="11" x2="10" y2="17" />
              <line x1="14" y1="11" x2="14" y2="17" />
            </svg>
          </button>
        </div>
      ))}

      <button type="button" className="btn btn-sm" onClick={addRow} style={{ marginTop: rows.length ? 2 : 4 }}>
        {t('addOptionButton')}
      </button>
    </div>
  )
}
