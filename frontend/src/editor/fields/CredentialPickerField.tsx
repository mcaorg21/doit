import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { credentialsApi } from '../../api/credentials'
import { ApiError } from '../../api/client'
import { PAIR_TYPES } from '../credentialTypes'
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
  const queryClient = useQueryClient()
  const { data: credentials } = useQuery({
    queryKey: ['credentials', projectId],
    queryFn: () => credentialsApi.list(projectId),
  })

  // Case-insensitive: the Type field is free text, so a credential saved as
  // "OpenAI" (or with stray whitespace) should still match a "openai" filter.
  const wantedType = (spec.credentialType ?? '').trim().toLowerCase()
  const matching = (credentials ?? []).filter((c) => c.type.trim().toLowerCase() === wantedType)
  const isPairType = PAIR_TYPES.has(wantedType)

  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [pairLogin, setPairLogin] = useState('')
  const [pairPassword, setPairPassword] = useState('')
  const [singleValue, setSingleValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  function startCreate() {
    setName('')
    setPairLogin('')
    setPairPassword('')
    setSingleValue('')
    setError(null)
    setCreating(true)
  }

  const createMutation = useMutation({
    mutationFn: () => {
      const finalValue = isPairType ? `${pairLogin.trim()}:${pairPassword.trim()}` : singleValue.trim()
      return credentialsApi.create(projectId, name.trim(), spec.credentialType ?? '', finalValue)
    },
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['credentials', projectId] })
      onChange(created.id)
      setCreating(false)
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Failed to create credential')
    },
  })

  const canSave = name.trim() !== '' && (isPairType ? pairLogin.trim() !== '' && pairPassword.trim() !== '' : singleValue.trim() !== '')

  return (
    <div className="field">
      <label>
        {spec.label}
        {spec.required ? ' *' : ''}
      </label>
      <div style={{ display: 'flex', gap: 6 }}>
        <select value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} style={{ flex: 1 }}>
          <option value="">Select a credential…</option>
          {matching.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <button type="button" className="btn btn-sm" onClick={startCreate} title={`Create a new "${spec.credentialType}" credential`}>
          + New
        </button>
      </div>
      {matching.length === 0 && (
        <span className="hint">
          No "{spec.credentialType}" credential yet — click "+ New" above, or add one from the Credentials button on
          the project page.
        </span>
      )}

      {creating && (
        <div className="modal-overlay" onClick={() => setCreating(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>New "{spec.credentialType}" credential</h3>
            <div className="field">
              <label>Name</label>
              <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. prod-account" />
            </div>
            {isPairType ? (
              <>
                <div className="field">
                  <label>Login</label>
                  <input value={pairLogin} onChange={(e) => setPairLogin(e.target.value)} placeholder="username" />
                </div>
                <div className="field">
                  <label>Password</label>
                  <input type="password" value={pairPassword} onChange={(e) => setPairPassword(e.target.value)} placeholder="password" />
                </div>
              </>
            ) : (
              <div className="field">
                <label>Value</label>
                <input type="password" value={singleValue} onChange={(e) => setSingleValue(e.target.value)} placeholder="API key / token / secret" />
              </div>
            )}
            {error && <div className="error-banner">{error}</div>}
            <div className="modal-actions">
              <button className="btn" onClick={() => setCreating(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" disabled={!canSave || createMutation.isPending} onClick={() => createMutation.mutate()}>
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
