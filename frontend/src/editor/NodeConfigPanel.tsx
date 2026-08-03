import type { Node } from '@xyflow/react'
import { fieldComponents } from './fields'
import type { FlowNodeData } from './types'
import type { NodeTypeSpec, ParamFieldSpec } from '../types/nodeType'

interface Props {
  node: Node<FlowNodeData> | null
  spec: NodeTypeSpec | undefined
  onChangeParam: (key: string, value: unknown) => void
  onChangeMeta: (key: 'title' | 'note', value: string) => void
  onDeleteNode: () => void
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

export default function NodeConfigPanel({ node, spec, onChangeParam, onChangeMeta, onDeleteNode }: Props) {
  if (!node || !spec) {
    return <div className="node-config-empty">Select a node to configure it.</div>
  }

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
        <label>Note (what does this node do?)</label>
        <textarea
          value={node.data.note ?? ''}
          placeholder="Explain what this node is for…"
          rows={3}
          onChange={(e) => onChangeMeta('note', e.target.value)}
        />
        <span className="hint">Shown as a comment above this node's code, and as a tooltip on the canvas.</span>
      </div>
      <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '12px 0' }} />

      {spec.params.map((paramSpec) => {
        const FieldComponent = fieldComponents[paramSpec.type]
        const fieldSpec: ParamFieldSpec =
          paramSpec.key === 'selector'
            ? {
                ...paramSpec,
                placeholder:
                  SELECTOR_TYPE_PLACEHOLDERS[String(node.data.params.selectorType ?? 'css')] ?? paramSpec.placeholder,
              }
            : paramSpec

        return (
          <FieldComponent
            key={paramSpec.key}
            spec={fieldSpec}
            value={node.data.params[paramSpec.key] ?? paramSpec.default}
            onChange={(value) => onChangeParam(paramSpec.key, value)}
          />
        )
      })}
    </div>
  )
}
