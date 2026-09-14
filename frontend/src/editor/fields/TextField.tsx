import type { ParamFieldSpec } from '../../types/nodeType'
import { genRandomToken } from '../randomToken'
import type { FieldMapOption } from '../graph'
import { useLanguage } from '../../i18n/LanguageContext'

export interface FieldProps {
  spec: ParamFieldSpec
  value: unknown
  onChange: (value: unknown) => void
  insertOptions?: FieldMapOption[]
}

export default function TextField({ spec, value, onChange, insertOptions }: FieldProps) {
  const { t } = useLanguage()
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
        <>
          <span className="hint">{t('templateSupportHint')}</span>
          {insertOptions && insertOptions.length > 0 && (
            <select
              value=""
              title={t('insertVariableTitle')}
              onChange={(e) => {
                if (!e.target.value) return
                const current = (value as string) ?? ''
                onChange(current ? `${current} ${e.target.value}` : e.target.value)
                e.target.value = ''
              }}
              style={{ marginTop: 4, fontSize: 12 }}
            >
              <option value="">{t('insertVariablePlaceholder')}</option>
              {insertOptions.map((opt) => (
                <option key={opt.expr} value={opt.expr}>
                  {opt.nodeLabel}: {opt.path}
                </option>
              ))}
            </select>
          )}
        </>
      )}
    </div>
  )
}
