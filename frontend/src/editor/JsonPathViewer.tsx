import { useState, type ReactNode } from 'react'

interface Props {
  value: unknown
  prefix: string
}

interface Line {
  key: string
  indent: number
  content: ReactNode
}

function Leaf({ value, expr, trailingComma }: { value: unknown; expr: string | null; trailingComma: boolean }) {
  const [copied, setCopied] = useState(false)
  const text = JSON.stringify(value)

  if (!expr) {
    return (
      <>
        {text}
        {trailingComma ? ',' : ''}
      </>
    )
  }

  return (
    <>
      <span
        title={copied ? 'Copied!' : expr}
        onClick={() => {
          navigator.clipboard?.writeText(expr).catch(() => {})
          setCopied(true)
          setTimeout(() => setCopied(false), 1200)
        }}
        style={{
          cursor: 'pointer',
          textDecoration: 'underline dotted',
          textDecorationColor: 'var(--text-muted)',
          color: copied ? 'var(--success)' : undefined,
        }}
      >
        {text}
      </span>
      {trailingComma ? ',' : ''}
    </>
  )
}

// Renders a parsed JSON value as an indented, line-per-field tree (rather than one
// giant JSON.stringify blob) so each leaf can carry its own hover tooltip / click-to-
// copy — showing exactly the {{prefix.path}} expression that would reference it from
// another node's template-capable field. See jsonPaths.ts for which paths are
// actually referenceable (a nested array's contents aren't — the template syntax has
// no numeric-index access).
function renderLines(
  value: unknown,
  segments: string[],
  referenceable: boolean,
  prefix: string,
  indent: number,
  keyPrefix: string,
  trailingComma: boolean,
): Line[] {
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return [{ key: keyPrefix, indent, content: `[]${trailingComma ? ',' : ''}` }]
    }
    const isTopLevel = segments.length === 0
    const lines: Line[] = [{ key: `${keyPrefix}-open`, indent, content: '[' }]
    value.forEach((el, i) => {
      lines.push(
        ...renderLines(el, segments, referenceable && isTopLevel, prefix, indent + 1, `${keyPrefix}-${i}`, i < value.length - 1),
      )
    })
    lines.push({ key: `${keyPrefix}-close`, indent, content: `]${trailingComma ? ',' : ''}` })
    return lines
  }

  if (value !== null && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.length === 0) {
      return [{ key: keyPrefix, indent, content: `{}${trailingComma ? ',' : ''}` }]
    }
    const lines: Line[] = [{ key: `${keyPrefix}-open`, indent, content: '{' }]
    entries.forEach(([k, v], i) => {
      const isLast = i === entries.length - 1
      const subLines = renderLines(v, [...segments, k], referenceable, prefix, indent + 1, `${keyPrefix}-${k}`, false)
      subLines[0] = {
        ...subLines[0],
        content: (
          <>
            <span style={{ color: 'var(--accent)' }}>&quot;{k}&quot;</span>: {subLines[0].content}
          </>
        ),
      }
      if (!isLast) {
        const lastIdx = subLines.length - 1
        subLines[lastIdx] = { ...subLines[lastIdx], content: <>{subLines[lastIdx].content},</> }
      }
      lines.push(...subLines)
    })
    lines.push({ key: `${keyPrefix}-close`, indent, content: `}${trailingComma ? ',' : ''}` })
    return lines
  }

  const expr = referenceable && segments.length > 0 ? `{{${prefix}.${segments.join('.')}}}` : null
  return [{ key: keyPrefix, indent, content: <Leaf value={value} expr={expr} trailingComma={trailingComma} /> }]
}

export default function JsonPathViewer({ value, prefix }: Props) {
  const lines = renderLines(value, [], true, prefix, 0, 'root', false)
  return (
    <div style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>
      {lines.map((line) => (
        <div key={line.key} style={{ paddingLeft: line.indent * 14, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
          {line.content}
        </div>
      ))}
    </div>
  )
}
