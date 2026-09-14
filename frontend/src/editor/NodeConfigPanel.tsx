import { useEffect, useState } from 'react'
import type { Node } from '@xyflow/react'
import { fieldComponents } from './fields'
import VariablePickerField from './fields/VariablePickerField'
import CredentialPickerField from './fields/CredentialPickerField'
import type { FlowNodeData } from './types'
import type { FieldMapOption, VariableSource } from './graph'
import type { NodeTypeSpec, ParamFieldSpec, VisibleWhenCondition } from '../types/nodeType'
import { useLanguage, type TranslationKey } from '../i18n/LanguageContext'
import { translateNodeSpec, translateParamSpec } from '../i18n/useNodeText'

interface Props {
  node: Node<FlowNodeData> | null
  spec: NodeTypeSpec | undefined
  onChangeParam: (key: string, value: unknown) => void
  onChangeMeta: (key: 'title' | 'note', value: string) => void
  onChangeResultType: (paramKey: string, resultType: string) => void
  onDeleteNode: () => void
  upstreamVariables: VariableSource[]
  onPreviewVariable: (source: VariableSource) => Promise<unknown>
  upstreamFieldMapOptions: FieldMapOption[]
  projectId: string
}

const RESULT_TYPE_OPTIONS = ['auto', 'string', 'array', 'object'] as const
type ResultType = (typeof RESULT_TYPE_OPTIONS)[number]

// Shown right under a producesVariable field (usually "Result Variable") — lets the
// human declare the variable's shape up front (so a downstream field can offer
// object-path suggestions before this node has ever run) and shows the real example
// value captured the last time it actually did run (see
// backend/app/execution/runner.py's __NODE_RESULT__ marker capture).
function ResultVariableExtras({
  resultType,
  example,
  hasExample,
  onChangeType,
  t,
}: {
  resultType: ResultType
  example: unknown
  hasExample: boolean
  onChangeType: (value: string) => void
  t: (key: TranslationKey) => string
}) {
  return (
    <div className="field" style={{ marginTop: -6 }}>
      <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>{t('resultTypeLabel')}</label>
      <select value={resultType} onChange={(e) => onChangeType(e.target.value)} style={{ fontSize: 12 }}>
        {RESULT_TYPE_OPTIONS.map((opt) => (
          <option key={opt} value={opt}>
            {t(`resultType_${opt}` as TranslationKey)}
          </option>
        ))}
      </select>
      {hasExample ? (
        <>
          <span className="hint">{t('resultExampleLabel')}</span>
          <pre
            style={{
              marginTop: 4,
              fontFamily: 'var(--mono)',
              fontSize: 12,
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              padding: '6px 8px',
              borderRadius: 6,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
              maxHeight: 160,
              overflowY: 'auto',
            }}
          >
            {JSON.stringify(example, null, 2)}
          </pre>
        </>
      ) : (
        <span className="hint">{t('resultExampleEmpty')}</span>
      )}
    </div>
  )
}

// The "selector" field's example depends on which locator strategy is selected in the
// sibling "selectorType" field — a plain example like "email" is misleading once XPath
// is chosen, since a real XPath needs a full expression, not a bare name.
const SELECTOR_TYPE_PLACEHOLDERS: Record<string, string> = {
  css: '#email, .btn, input[name=x]',
  id: 'email',
  class_name: 'btn-primary',
  xpath: "//input[@id='email']",
  full_xpath: '/html/body/div[1]/form/input[2]',
}

function conditionMet(condition: VisibleWhenCondition, allParams: ParamFieldSpec[], values: Record<string, unknown>) {
  const dep = allParams.find((p) => p.key === condition.key)
  const value = values[condition.key] ?? dep?.default
  if (condition.in) return condition.in.includes(value)
  return value === condition.equals
}

function isFieldVisible(paramSpec: ParamFieldSpec, allParams: ParamFieldSpec[], values: Record<string, unknown>) {
  if (!paramSpec.visibleWhen) return true
  const conditions = Array.isArray(paramSpec.visibleWhen) ? paramSpec.visibleWhen : [paramSpec.visibleWhen]
  return conditions.every((c) => conditionMet(c, allParams, values))
}

export default function NodeConfigPanel({
  node,
  spec,
  onChangeParam,
  onChangeMeta,
  onChangeResultType,
  onDeleteNode,
  upstreamVariables,
  onPreviewVariable,
  upstreamFieldMapOptions,
  projectId,
}: Props) {
  const [noteOpen, setNoteOpen] = useState(false)
  const { language, t } = useLanguage()

  // Starts collapsed again for every newly selected node — closed by default is the
  // point (it otherwise eats vertical space in the side panel for a field most nodes
  // never use), not "remembers whichever node you last opened it on".
  useEffect(() => {
    setNoteOpen(false)
  }, [node?.id])

  if (!node || !spec) {
    return <div className="node-config-empty">{t('selectNodePrompt')}</div>
  }

  const specText = translateNodeSpec(spec, language)

  // Every upstream field the user can reference in a {{...}} field: whole variables
  // an earlier node produced (e.g. Get Text's Result Variable), plus any nested
  // paths saved via an HTTP Request node's "Save Mapping" button.
  const insertOptions: FieldMapOption[] = [
    ...upstreamVariables.map((v) => ({ nodeLabel: v.nodeLabel, path: v.variableName, expr: `{{${v.variableName}}}` })),
    ...upstreamFieldMapOptions,
  ]

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
        <h3 style={{ marginTop: 0 }}>{specText.label}</h3>
        <button className="btn btn-sm" onClick={onDeleteNode} title={t('deleteNodeTitle')}>
          {t('delete')}
        </button>
      </div>
      <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: -8 }}>{specText.description}</p>

      <div className="field">
        <label>{t('titleFieldLabel')}</label>
        <input
          value={node.data.title ?? ''}
          placeholder={specText.label}
          onChange={(e) => onChangeMeta('title', e.target.value)}
        />
      </div>
      <div className="field">
        <label
          onClick={() => setNoteOpen((v) => !v)}
          style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, userSelect: 'none' }}
        >
          <span style={{ display: 'inline-block', transform: noteOpen ? 'rotate(90deg)' : undefined, transition: 'transform 0.1s' }}>
            ▸
          </span>
          {t('noteFieldLabel')}
          {!noteOpen && node.data.note?.trim() && (
            <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>{t('noteSetSuffix')}</span>
          )}
        </label>
        {noteOpen && (
          <>
            <textarea
              value={node.data.note ?? ''}
              placeholder={t('notePlaceholder')}
              rows={3}
              onChange={(e) => onChangeMeta('note', e.target.value)}
            />
            <span className="hint">{t('noteHint')}</span>
          </>
        )}
      </div>
      <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '12px 0' }} />

      {spec.params.map((paramSpec) => {
        if (!isFieldVisible(paramSpec, spec.params, node.data.params)) {
          return null
        }

        if (paramSpec.consumesVariable) {
          return (
            <VariablePickerField
              key={paramSpec.key}
              spec={translateParamSpec(paramSpec, language)}
              value={node.data.params[paramSpec.key] ?? paramSpec.default}
              onChange={(value) => onChangeParam(paramSpec.key, value)}
              sources={upstreamVariables}
              onPreview={onPreviewVariable}
            />
          )
        }

        if (paramSpec.credentialType) {
          return (
            <CredentialPickerField
              key={paramSpec.key}
              spec={translateParamSpec(paramSpec, language)}
              value={node.data.params[paramSpec.key] ?? paramSpec.default}
              onChange={(value) => onChangeParam(paramSpec.key, value)}
              projectId={projectId}
            />
          )
        }

        const FieldComponent = fieldComponents[paramSpec.type]
        let fieldSpec: ParamFieldSpec = paramSpec
        if (paramSpec.key === 'selector') {
          fieldSpec = {
            ...fieldSpec,
            placeholder:
              SELECTOR_TYPE_PLACEHOLDERS[String(node.data.params.selectorType ?? 'css')] ?? fieldSpec.placeholder,
          }
        }
        if (paramSpec.optionsSource) {
          const depValue = String(node.data.params[paramSpec.optionsSource.key] ?? '')
          fieldSpec = { ...fieldSpec, options: paramSpec.optionsSource.map[depValue] ?? [] }
        }
        fieldSpec = translateParamSpec(fieldSpec, language)

        return (
          <div key={paramSpec.key}>
            <FieldComponent
              spec={fieldSpec}
              value={node.data.params[paramSpec.key] ?? paramSpec.default}
              onChange={(value) => onChangeParam(paramSpec.key, value)}
              insertOptions={paramSpec.supportsTemplate ? insertOptions : undefined}
            />
            {paramSpec.producesVariable && (
              <ResultVariableExtras
                resultType={(node.data.resultTypes?.[paramSpec.key] as ResultType) ?? 'auto'}
                example={node.data.resultExamples?.[paramSpec.key]}
                hasExample={
                  !!node.data.resultExamples && Object.prototype.hasOwnProperty.call(node.data.resultExamples, paramSpec.key)
                }
                onChangeType={(value) => onChangeResultType(paramSpec.key, value)}
                t={t}
              />
            )}
          </div>
        )
      })}

      {node.data.nodeType === 'webhook_trigger' && (
        <div className="field">
          <label>{t('fullUrlLabel')}</label>
          {(() => {
            const method = String(node.data.params.method ?? 'POST')
            const path = String(node.data.params.path ?? '').trim().replace(/^\/+|\/+$/g, '')
            const secret = String(node.data.params.secret ?? '').trim()
            const route = `/api/webhooks/${path || '<path>'}/${secret || '<secret>'}`
            return (
              <>
                <input readOnly value={`${window.location.origin}${route}`} style={{ fontFamily: 'var(--mono)', fontSize: 12 }} />
                <span className="hint">
                  {method} {route} — {t('webhookOnlyRespondsHint')}
                </span>
              </>
            )
          })()}
        </div>
      )}
    </div>
  )
}
