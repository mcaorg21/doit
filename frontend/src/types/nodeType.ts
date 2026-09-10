export type FieldType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'select'
  | 'boolean'
  | 'fieldList'
  | 'clickList'
  | 'keyValueList'
  | 'fileList'
export type NodeCategory = 'trigger' | 'dataSource' | 'browser' | 'action' | 'logic' | 'function'

export interface ParamFieldOption {
  value: string
  label: string
}

export type VisibleWhenCondition = { key: string; equals?: unknown; in?: unknown[] }

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
  visibleWhen: VisibleWhenCondition | VisibleWhenCondition[] | null
  optionsSource: { key: string; map: Record<string, ParamFieldOption[]> } | null
  autoGenerate: boolean
  credentialType: string | null
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
