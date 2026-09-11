import type { ComponentType } from 'react'
import type { FieldType } from '../../types/nodeType'
import TextField, { type FieldProps } from './TextField'
import NumberField from './NumberField'
import SelectField from './SelectField'
import BooleanField from './BooleanField'
import FieldListField from './FieldListField'
import ClickListField from './ClickListField'
import KeyValueListField from './KeyValueListField'
import FileListField from './FileListField'
import TextListField from './TextListField'

export const fieldComponents: Record<FieldType, ComponentType<FieldProps>> = {
  text: TextField,
  textarea: TextField,
  number: NumberField,
  select: SelectField,
  boolean: BooleanField,
  fieldList: FieldListField,
  clickList: ClickListField,
  keyValueList: KeyValueListField,
  fileList: FileListField,
  textList: TextListField,
}
