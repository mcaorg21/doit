export type FieldType = 'text' | 'textarea' | 'number' | 'select' | 'boolean' | 'fieldList'
export type NodeCategory = 'trigger' | 'dataSource' | 'browser' | 'action' | 'logic'

export interface ParamFieldOption {
  value: string
  label: string
}

export interface ParamFieldSpec {
  key: string
  label: string
  type: FieldType
  required: boolean
  default: unknown
  options: ParamFieldOption[] | null
  placeholder: string | null
  supportsTemplate: boolean
  producesVariable: boolean
  consumesVariable: boolean
  visibleWhen: { key: string; equals?: unknown; in?: unknown[] } | null
  optionsSource: { key: string; map: Record<string, ParamFieldOption[]> } | null
  autoGenerate: boolean
}

export interface NodeTypeSpec {
  type: string
  label: string
  category: NodeCategory
  description: string
  icon: string | null
  isBranch: boolean
  params: ParamFieldSpec[]
}
