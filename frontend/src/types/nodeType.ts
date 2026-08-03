export type FieldType = 'text' | 'textarea' | 'number' | 'select' | 'boolean'
export type NodeCategory = 'dataSource' | 'browser' | 'action' | 'logic'

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
