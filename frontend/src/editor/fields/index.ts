import type { ComponentType } from 'react'
import type { FieldType } from '../../types/nodeType'
import TextField, { type FieldProps } from './TextField'
import NumberField from './NumberField'
import SelectField from './SelectField'
import BooleanField from './BooleanField'

export const fieldComponents: Record<FieldType, ComponentType<FieldProps>> = {
  text: TextField,
  textarea: TextField,
  number: NumberField,
  select: SelectField,
  boolean: BooleanField,
}
