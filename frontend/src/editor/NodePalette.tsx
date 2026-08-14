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

interface Props {
  onAddNode: (spec: NodeTypeSpec) => void
}

export default function NodePalette({ onAddNode }: Props) {
  const { data: nodeTypes } = useQuery({
    queryKey: ['node-types'],
    queryFn: nodeTypesApi.list,
  })

  const byCategory = new Map<NodeCategory, typeof nodeTypes>()
  for (const spec of nodeTypes ?? []) {
    const list = byCategory.get(spec.category) ?? []
    list.push(spec)
    byCategory.set(spec.category, list)
  }

  return (
    <div className="palette">
      {(['trigger', 'dataSource', 'browser', 'action', 'logic', 'function'] as NodeCategory[]).map((category) => {
        const specs = byCategory.get(category)
        if (!specs || specs.length === 0) return null
        return (
          <div key={category}>
            <h3>{CATEGORY_LABELS[category]}</h3>
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
        )
      })}
    </div>
  )
}
