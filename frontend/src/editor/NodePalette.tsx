import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { nodeTypesApi } from '../api/nodeTypes'
import { useLanguage } from '../i18n/LanguageContext'
import { translateNodeSpec } from '../i18n/useNodeText'
import type { TranslationKey } from '../i18n/LanguageContext'
import type { NodeCategory, NodeTypeSpec } from '../types/nodeType'

const CATEGORY_LABEL_KEYS: Record<NodeCategory, TranslationKey> = {
  trigger: 'categoryTriggers',
  dataSource: 'categoryDataSources',
  browser: 'categoryBrowser',
  action: 'categoryActions',
  logic: 'categoryLogic',
  function: 'categoryFunctions',
}

const ALL_CATEGORIES: NodeCategory[] = ['trigger', 'dataSource', 'browser', 'action', 'logic', 'function']

const COLLAPSED_STORAGE_KEY = 'automation.palette.collapsedCategories'

function loadCollapsed(): Set<NodeCategory> {
  try {
    const raw = localStorage.getItem(COLLAPSED_STORAGE_KEY)
    if (raw) return new Set(JSON.parse(raw))
  } catch {
    // Private browsing / storage disabled — fall through to the default below.
  }
  // Default to every category collapsed — with this many node types now
  // registered, a fully-expanded palette on first load is mostly scrolling.
  return new Set(ALL_CATEGORIES)
}

function saveCollapsed(collapsed: Set<NodeCategory>) {
  try {
    localStorage.setItem(COLLAPSED_STORAGE_KEY, JSON.stringify([...collapsed]))
  } catch {
    // Private browsing / storage disabled — collapsing still works for this
    // session, it just won't be remembered next time.
  }
}

interface Props {
  onAddNode: (spec: NodeTypeSpec) => void
}

interface TooltipState {
  spec: NodeTypeSpec
  x: number
  y: number
}

export default function NodePalette({ onAddNode }: Props) {
  const { language, t } = useLanguage()
  const { data: nodeTypes } = useQuery({
    queryKey: ['node-types'],
    queryFn: nodeTypesApi.list,
  })

  const [collapsed, setCollapsed] = useState<Set<NodeCategory>>(loadCollapsed)
  // A custom tooltip (not the native `title=`, which is slow to appear and can't be
  // styled) — shows what a node type actually DOES plus a concrete example, so
  // someone browsing types can tell which one they want without adding it first.
  // Rendered via a portal straight onto <body> for the same reason GenericNode's
  // preview modal does: `.palette` has `overflow-y: auto`, which would clip a
  // tooltip wide enough to need to spill past the sidebar's right edge.
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  function toggleCategory(category: NodeCategory) {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(category)) next.delete(category)
      else next.add(category)
      saveCollapsed(next)
      return next
    })
  }

  const byCategory = new Map<NodeCategory, typeof nodeTypes>()
  for (const spec of nodeTypes ?? []) {
    const list = byCategory.get(spec.category) ?? []
    list.push(spec)
    byCategory.set(spec.category, list)
  }

  return (
    <div className="palette">
      {ALL_CATEGORIES.map((category) => {
        const specs = byCategory.get(category)
        if (!specs || specs.length === 0) return null
        const isCollapsed = collapsed.has(category)
        return (
          <div key={category} className="palette-category">
            <button
              type="button"
              className="palette-category-header"
              onClick={() => toggleCategory(category)}
              aria-expanded={!isCollapsed}
            >
              <svg
                width="10"
                height="10"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="palette-category-chevron"
                style={{ transform: isCollapsed ? 'rotate(-90deg)' : undefined }}
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
              <span>{t(CATEGORY_LABEL_KEYS[category])}</span>
              <span className="palette-category-count">{specs.length}</span>
            </button>
            {!isCollapsed && (
              <div className="palette-category-items">
                {specs.map((spec) => (
                  <div
                    key={spec.type}
                    className="palette-item"
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData('application/x-automation-node-type', spec.type)
                      e.dataTransfer.effectAllowed = 'move'
                      setTooltip(null)
                    }}
                    onClick={() => onAddNode(spec)}
                    onMouseEnter={(e) => setTooltip({ spec, x: e.clientX, y: e.clientY })}
                    onMouseMove={(e) => setTooltip((prev) => (prev && prev.spec.type === spec.type ? { ...prev, x: e.clientX, y: e.clientY } : prev))}
                    onMouseLeave={() => setTooltip((prev) => (prev?.spec.type === spec.type ? null : prev))}
                  >
                    {translateNodeSpec(spec, language).label}
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}

      {tooltip &&
        (() => {
          const text = translateNodeSpec(tooltip.spec, language)
          return createPortal(
            <div className="palette-tooltip" style={{ left: tooltip.x + 16, top: tooltip.y + 12 }}>
              <div className="palette-tooltip-title">{text.label}</div>
              <div className="palette-tooltip-desc">{text.description}</div>
              {text.example && (
                <div className="palette-tooltip-example">
                  <span className="palette-tooltip-example-label">{t('exampleLabel')}</span>
                  {text.example}
                </div>
              )}
            </div>,
            document.body,
          )
        })()}
    </div>
  )
}
