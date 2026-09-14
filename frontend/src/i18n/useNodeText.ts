import { useLanguage } from './LanguageContext'
import { nodeCatalogPt } from './nodeCatalog'
import { paramLabelsPt, paramOptionsPt } from './paramLabels'
import type { NodeTypeSpec, ParamFieldSpec } from '../types/nodeType'

export interface NodeText {
  label: string
  description: string
  example: string
}

// Applies the Portuguese catalog overrides (see nodeCatalog.ts) on top of a node
// type's English spec when the UI language is 'pt' — the spec itself (from
// GET /api/node-types) always stays English, this only affects what's displayed.
export function translateNodeSpec(spec: Pick<NodeTypeSpec, 'type' | 'label' | 'description' | 'example'>, language: 'en' | 'pt'): NodeText {
  if (language === 'pt') {
    const override = nodeCatalogPt[spec.type]
    if (override) return override
  }
  return { label: spec.label, description: spec.description, example: spec.example ?? '' }
}

export function useNodeText(spec: Pick<NodeTypeSpec, 'type' | 'label' | 'description' | 'example'> | null | undefined): NodeText {
  const { language } = useLanguage()
  if (!spec) return { label: '', description: '', example: '' }
  return translateNodeSpec(spec, language)
}

// Applies the Portuguese overrides for a single param FIELD's own label and select
// options (see paramLabels.ts) — a separate, text-keyed layer from
// translateNodeSpec's node-level label/description/example, since most param
// labels ("Selector Value", "Result Variable", ...) and select option values
// (css/id/xpath/...) repeat verbatim across many node types. Falls back to the
// original English text for anything not in the dictionary (e.g. a brand new
// node/param this translation pass hasn't caught up with yet).
export function translateParamSpec(spec: ParamFieldSpec, language: 'en' | 'pt'): ParamFieldSpec {
  if (language !== 'pt') return spec
  const label = paramLabelsPt[spec.label] ?? spec.label
  const options = spec.options
    ? spec.options.map((o) => ({ ...o, label: paramOptionsPt[o.value] ?? o.label }))
    : spec.options
  if (label === spec.label && options === spec.options) return spec
  return { ...spec, label, options }
}
