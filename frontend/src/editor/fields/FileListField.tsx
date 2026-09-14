import type { FieldProps } from './TextField'
import { useLanguage } from '../../i18n/LanguageContext'

interface FileRow {
  filename: string
  value: string
}

function emptyRow(): FileRow {
  return { filename: '', value: '' }
}

// Repeatable {filename, value} rows for Save Files — filename is what the file gets
// called on disk, value is the base64 content (typically an HTTP Request node's
// "File" response, or a variable from an earlier node). Same array-as-value,
// no-extra-encoding pattern as KeyValueListField/FieldListField.
export default function FileListField({ spec, value, onChange }: FieldProps) {
  const { t } = useLanguage()
  const rows: FileRow[] = Array.isArray(value) ? (value as FileRow[]) : []

  function updateRow(index: number, patch: Partial<FileRow>) {
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
      {rows.length === 0 && <span className="hint">{t('noneYetHint')}</span>}

      {rows.map((row, i) => (
        <div key={i} className="field-list-row">
          <div className="field-list-row-pair">
            <input
              placeholder="Filename, e.g. documento.pdf"
              value={row.filename}
              onChange={(e) => updateRow(i, { filename: e.target.value })}
            />
            <input
              placeholder="Content (base64), e.g. {{httpNode.base64Var}}"
              value={row.value}
              onChange={(e) => updateRow(i, { value: e.target.value })}
            />
            <button
              type="button"
              className="icon-btn icon-btn-danger"
              title={t('removeTitle')}
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
        {t('addGenericButton')}
      </button>
      <span className="hint">{t('fileListBase64Hint')}</span>
    </div>
  )
}
