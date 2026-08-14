import { useQuery } from '@tanstack/react-query'
import { credentialsApi } from '../../api/credentials'
import type { ParamFieldSpec } from '../../types/nodeType'

interface Props {
  spec: ParamFieldSpec
  value: unknown
  onChange: (value: unknown) => void
  projectId: string
}

// Renders a dropdown of the project's Credentials, filtered to spec.credentialType
// (see ParamField.credentialType on the backend) — the field stores the credential's
// id; the node's own codegen resolves that id to the actual secret value.
export default function CredentialPickerField({ spec, value, onChange, projectId }: Props) {
  const { data: credentials } = useQuery({
    queryKey: ['credentials', projectId],
    queryFn: () => credentialsApi.list(projectId),
  })

  // Case-insensitive: the Type field is free text, so a credential saved as
  // "OpenAI" (or with stray whitespace) should still match a "openai" filter.
  const wantedType = (spec.credentialType ?? '').trim().toLowerCase()
  const matching = (credentials ?? []).filter((c) => c.type.trim().toLowerCase() === wantedType)

  return (
    <div className="field">
      <label>
        {spec.label}
        {spec.required ? ' *' : ''}
      </label>
      <select value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)}>
        <option value="">Select a credential…</option>
        {matching.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      {matching.length === 0 && (
        <span className="hint">
          No "{spec.credentialType}" credential yet — add one from the Credentials button on the project page.
        </span>
      )}
    </div>
  )
}
