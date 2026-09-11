import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { credentialsApi } from '../api/credentials'
import type { Credential } from '../types/workflow'
import { ApiError } from '../api/client'

interface Props {
  projectId: string
  onClose: () => void
}

const TYPE_PRESETS = ['2captcha', '2captcha_browser', 'openai', 'anthropic', 'totp', 'login']
const CUSTOM_TYPE = '__custom__'

// Most credential types are just "paste the API key" into one Value field — these
// need two secrets at once, so they get dedicated Login/Password inputs instead of
// making the user type a "login:password" string into a single field by hand. The
// two pieces are still packed into one "login:password" string for storage (the
// Credential model only has one Value field), just assembled here, not by the user.
const PAIR_TYPES = new Set(['2captcha_browser', 'login'])

export default function CredentialsManager({ projectId, onClose }: Props) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<Credential | 'new' | null>(null)
  const [name, setName] = useState('')
  const [type, setType] = useState('')
  // A free-text Type field let someone type "apikey" as a label for an OpenAI key
  // instead of the exact string a node's credentialType filter looks for ("openai")
  // — the credential existed, matched nothing, and looked like a bug. A real <select>
  // for the known types makes that typo class impossible; "Custom…" still allows any
  // string for credential types this app doesn't know about yet.
  const [useCustomType, setUseCustomType] = useState(false)
  const [value, setValue] = useState('')
  const [pairLogin, setPairLogin] = useState('')
  const [pairPassword, setPairPassword] = useState('')
  const [revealed, setRevealed] = useState<Set<string>>(new Set())
  const [confirmDelete, setConfirmDelete] = useState<Credential | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isPairType = PAIR_TYPES.has(type)

  const { data: credentials, isLoading } = useQuery({
    queryKey: ['credentials', projectId],
    queryFn: () => credentialsApi.list(projectId),
  })

  function startNew() {
    setEditing('new')
    setName('')
    setType('')
    setUseCustomType(false)
    setValue('')
    setPairLogin('')
    setPairPassword('')
    setError(null)
  }

  function startEdit(c: Credential) {
    setEditing(c)
    setName(c.name)
    setType(c.type)
    setUseCustomType(!TYPE_PRESETS.includes(c.type))
    setValue(c.value)
    // Split on the FIRST colon only, matching the backend's parsing — a password
    // containing its own colon shouldn't get truncated.
    const colonIndex = c.value.indexOf(':')
    setPairLogin(colonIndex === -1 ? c.value : c.value.slice(0, colonIndex))
    setPairPassword(colonIndex === -1 ? '' : c.value.slice(colonIndex + 1))
    setError(null)
  }

  function toggleReveal(id: string) {
    setRevealed((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const saveMutation = useMutation({
    mutationFn: () => {
      // Lowercased so it reliably matches a node's credentialType filter (e.g.
      // "openai") regardless of how the user capitalized it here — the field is
      // free text with just a datalist of suggestions, nothing stops "OpenAI".
      const normalizedType = type.trim().toLowerCase()
      const finalValue = isPairType ? `${pairLogin.trim()}:${pairPassword.trim()}` : value
      if (editing === 'new') return credentialsApi.create(projectId, name.trim(), normalizedType, finalValue)
      if (editing) return credentialsApi.update(projectId, editing.id, name.trim(), normalizedType, finalValue)
      return Promise.reject(new Error('Nothing to save'))
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credentials', projectId] })
      setEditing(null)
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Failed to save credential')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => credentialsApi.remove(projectId, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credentials', projectId] })
      setConfirmDelete(null)
    },
  })

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 520 }}>
        <h3>Credentials</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: 12, margin: '0 0 10px' }}>
          Secrets (API keys, tokens...) that nodes in this project can reference — e.g. a 2Captcha node's API key.
          Stored per-project, plain in this project's data folder.
        </p>

        {isLoading && <p style={{ fontSize: 13 }}>Loading…</p>}
        {!isLoading && (!credentials || credentials.length === 0) && editing === null && (
          <div className="empty-state" style={{ padding: '20px 0' }}>
            No credentials yet.
          </div>
        )}

        {editing === null && credentials && credentials.length > 0 && (
          <div className="list" style={{ marginBottom: 12 }}>
            {credentials.map((c) => (
              <div key={c.id} className="list-item">
                <div>
                  <div className="list-item-title">{c.name}</div>
                  <div className="list-item-meta">
                    {c.type || '(no type)'} ·{' '}
                    <span style={{ fontFamily: 'var(--mono)' }}>
                      {revealed.has(c.id) ? c.value : '•'.repeat(Math.min(c.value.length, 20)) || '(empty)'}
                    </span>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <button className="icon-btn" title={revealed.has(c.id) ? 'Hide value' : 'Show value'} onClick={() => toggleReveal(c.id)}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      {revealed.has(c.id) ? (
                        <>
                          <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
                          <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
                          <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
                          <line x1="2" y1="2" x2="22" y2="22" />
                        </>
                      ) : (
                        <>
                          <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
                          <circle cx="12" cy="12" r="3" />
                        </>
                      )}
                    </svg>
                  </button>
                  <button className="icon-btn" title="Edit" onClick={() => startEdit(c)}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 20h9" />
                      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" />
                    </svg>
                  </button>
                  <button className="icon-btn icon-btn-danger" title="Delete" onClick={() => setConfirmDelete(c)}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      <line x1="10" y1="11" x2="10" y2="17" />
                      <line x1="14" y1="11" x2="14" y2="17" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {editing !== null && (
          <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
            <div className="field">
              <label>Name</label>
              <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. My 2Captcha Key" />
            </div>
            <div className="field">
              <label>Type</label>
              <select
                value={useCustomType ? CUSTOM_TYPE : type}
                onChange={(e) => {
                  if (e.target.value === CUSTOM_TYPE) {
                    setUseCustomType(true)
                    setType('')
                  } else {
                    setUseCustomType(false)
                    setType(e.target.value)
                  }
                }}
              >
                <option value="" disabled>
                  Select a type…
                </option>
                {TYPE_PRESETS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
                <option value={CUSTOM_TYPE}>Custom…</option>
              </select>
              {useCustomType && (
                <input
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                  placeholder="e.g. my-service"
                  style={{ marginTop: 6 }}
                />
              )}
              <span className="hint">
                Must match exactly what a node's credential field expects (e.g. the 2Captcha node only lists
                "2captcha" credentials) — pick one of the known types above rather than typing your own label.
              </span>
            </div>
            {isPairType ? (
              <>
                <div className="field">
                  <label>Login</label>
                  <input value={pairLogin} onChange={(e) => setPairLogin(e.target.value)} placeholder="e.g. bc034b8f781cab8ae0f3" />
                </div>
                <div className="field">
                  <label>Password</label>
                  <input
                    type="password"
                    value={pairPassword}
                    onChange={(e) => setPairPassword(e.target.value)}
                    placeholder="Password"
                  />
                  <span className="hint">From your 2Captcha Scraping Browser dashboard.</span>
                </div>
              </>
            ) : (
              <div className="field">
                <label>Value</label>
                <input type="password" value={value} onChange={(e) => setValue(e.target.value)} placeholder="API key / token / secret" />
              </div>
            )}
            {error && <div className="error-banner">{error}</div>}
            <div className="modal-actions">
              <button className="btn" onClick={() => setEditing(null)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={
                  !name.trim() ||
                  !type.trim() ||
                  (isPairType ? !pairLogin.trim() || !pairPassword.trim() : !value.trim()) ||
                  saveMutation.isPending
                }
                onClick={() => saveMutation.mutate()}
              >
                Save
              </button>
            </div>
          </div>
        )}

        <div className="modal-actions" style={{ justifyContent: 'space-between' }}>
          {editing === null ? (
            <button className="btn btn-sm" onClick={startNew}>
              + Add Credential
            </button>
          ) : (
            <span />
          )}
          <button className="btn btn-primary" onClick={onClose}>
            Close
          </button>
        </div>

        {confirmDelete && (
          <div className="modal-overlay" onClick={() => setConfirmDelete(null)}>
            <div className="modal" onClick={(e) => e.stopPropagation()}>
              <h3>Delete credential</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                Delete "{confirmDelete.name}"? Any node referencing it will fail to generate until you pick another.
              </p>
              <div className="modal-actions">
                <button className="btn" onClick={() => setConfirmDelete(null)}>
                  Cancel
                </button>
                <button className="btn btn-danger" disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate(confirmDelete.id)}>
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
