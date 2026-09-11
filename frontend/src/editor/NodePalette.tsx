import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { nodeTypesApi } from '../api/nodeTypes'
import type { NodeCategory, NodeTypeSpec } from '../types/nodeType'

const CATEGORY_LABELS: Record<NodeCategory, string> = {
  trigger: 'Triggers',
  dataSource: 'Data Sources',
  browser: 'Browser',
  action: 'Actions',
  logic: 'Logic',
  function: 'Functions',
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

export default function NodePalette({ onAddNode }: Props) {
  const { data: nodeTypes } = useQuery({
    queryKey: ['node-types'],
    queryFn: nodeTypesApi.list,
  })

  const [collapsed, setCollapsed] = useState<Set<NodeCategory>>(loadCollapsed)

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
              <span>{CATEGORY_LABELS[category]}</span>
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
                    }}
                    onClick={() => onAddNode(spec)}
                    title={spec.description}
                  >
                    {spec.label}
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
