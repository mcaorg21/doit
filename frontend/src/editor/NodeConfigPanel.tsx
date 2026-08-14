import { useEffect, useState } from 'react'
import type { Node } from '@xyflow/react'
import { fieldComponents } from './fields'
import VariablePickerField from './fields/VariablePickerField'
import CredentialPickerField from './fields/CredentialPickerField'
import type { FlowNodeData } from './types'
import type { FieldMapOption, VariableSource } from './graph'
import type { NodeTypeSpec, ParamFieldSpec } from '../types/nodeType'

interface Props {
  node: Node<FlowNodeData> | null
  spec: NodeTypeSpec | undefined
  onChangeParam: (key: string, value: unknown) => void
  onChangeMeta: (key: 'title' | 'note', value: string) => void
  onDeleteNode: () => void
  upstreamVariables: VariableSource[]
  onPreviewVariable: (source: VariableSource) => Promise<unknown>
  upstreamFieldMapOptions: FieldMapOption[]
  projectId: string
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

function isFieldVisible(paramSpec: ParamFieldSpec, allParams: ParamFieldSpec[], values: Record<string, unknown>) {
  if (!paramSpec.visibleWhen) return true
  const dep = allParams.find((p) => p.key === paramSpec.visibleWhen!.key)
  const value = values[paramSpec.visibleWhen.key] ?? dep?.default
  if (paramSpec.visibleWhen.in) return paramSpec.visibleWhen.in.includes(value)
  return value === paramSpec.visibleWhen.equals
}

export default function NodeConfigPanel({
  node,
  spec,
  onChangeParam,
  onChangeMeta,
  onDeleteNode,
  upstreamVariables,
  onPreviewVariable,
  upstreamFieldMapOptions,
  projectId,
}: Props) {
  const [noteOpen, setNoteOpen] = useState(false)

  // Starts collapsed again for every newly selected node — closed by default is the
  // point (it otherwise eats vertical space in the side panel for a field most nodes
  // never use), not "remembers whichever node you last opened it on".
  useEffect(() => {
    setNoteOpen(false)
  }, [node?.id])

  if (!node || !spec) {
    return <div className="node-config-empty">Select a node to configure it.</div>
  }

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
        <h3 style={{ marginTop: 0 }}>{spec.label}</h3>
        <button className="btn btn-sm" onClick={onDeleteNode} title="Delete node">
          Delete
        </button>
      </div>
      <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: -8 }}>{spec.description}</p>

      <div className="field">
        <label>Title (shown on the node in the canvas)</label>
        <input
          value={node.data.title ?? ''}
          placeholder={spec.label}
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
          Note (what does this node do?)
          {!noteOpen && node.data.note?.trim() && (
            <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(set)</span>
          )}
        </label>
        {noteOpen && (
          <>
            <textarea
              value={node.data.note ?? ''}
              placeholder="Explain what this node is for…"
              rows={3}
              onChange={(e) => onChangeMeta('note', e.target.value)}
            />
            <span className="hint">Shown as a comment above this node's code, and as a tooltip on the canvas.</span>
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
              spec={paramSpec}
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
              spec={paramSpec}
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

        return (
          <FieldComponent
            key={paramSpec.key}
            spec={fieldSpec}
            value={node.data.params[paramSpec.key] ?? paramSpec.default}
            onChange={(value) => onChangeParam(paramSpec.key, value)}
            insertOptions={paramSpec.supportsTemplate ? insertOptions : undefined}
          />
        )
      })}

      {node.data.nodeType === 'webhook_trigger' && (
        <div className="field">
          <label>Full URL</label>
          {(() => {
            const method = String(node.data.params.method ?? 'POST')
            const path = String(node.data.params.path ?? '').trim().replace(/^\/+|\/+$/g, '')
            const secret = String(node.data.params.secret ?? '').trim()
            const route = `/api/webhooks/${path || '<path>'}/${secret || '<secret>'}`
            return (
              <>
                <input readOnly value={`${window.location.origin}${route}`} style={{ fontFamily: 'var(--mono)', fontSize: 12 }} />
                <span className="hint">
                  {method} {route} — only responds while this workflow is Published (topbar toggle).
                </span>
              </>
            )
          })()}
        </div>
      )}
    </div>
  )
}
