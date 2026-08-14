import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { credentialsApi } from '../api/credentials'
import { foldersApi } from '../api/folders'
import { workflowsApi } from '../api/workflows'
import { llmImportApi, type ReconstructPythonResult } from '../api/llmImport'
import { ApiError } from '../api/client'
import type { Folder } from '../types/workflow'
import CredentialsManager from './CredentialsManager'

interface Props {
  projectId: string
  defaultFolderId: string | null
  onClose: () => void
}

const ELIGIBLE_TYPES = new Set(['openai', 'anthropic'])

function flattenFolders(folders: Folder[], parentId: string | null = null, depth = 0): { folder: Folder; depth: number }[] {
  const children = folders.filter((f) => f.parentId === parentId)
  return children.flatMap((f) => [{ folder: f, depth }, ...flattenFolders(folders, f.id, depth + 1)])
}

type Step = 'pick' | 'loading' | 'preview'

export default function PythonImportModal({ projectId, defaultFolderId, onClose }: Props) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [step, setStep] = useState<Step>('pick')
  const [credentialId, setCredentialId] = useState('')
  const [fileName, setFileName] = useState('')
  const [pythonCode, setPythonCode] = useState<string | null>(null)
  // Rendered as a sibling of this modal (not nested inside its overlay div) — if it
  // were nested, a click on the Credentials modal's own backdrop would close it AND
  // then bubble up to close this modal too, since click events bubble through
  // ancestor onClick handlers unless stopped.
  const [showCredentials, setShowCredentials] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [result, setResult] = useState<ReconstructPythonResult | null>(null)
  const [editableName, setEditableName] = useState('')
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(defaultFolderId)

  const { data: credentials } = useQuery({
    queryKey: ['credentials', projectId],
    queryFn: () => credentialsApi.list(projectId),
  })
  // Case-insensitive for the same reason as CredentialPickerField — Type is free text.
  const eligibleCredentials = (credentials ?? []).filter((c) => ELIGIBLE_TYPES.has(c.type.trim().toLowerCase()))

  const { data: folders } = useQuery({
    queryKey: ['folders', projectId],
    queryFn: () => foldersApi.list(projectId),
  })
  const flatFolders = flattenFolders(folders ?? [])

  const reconstructMutation = useMutation({
    mutationFn: () => llmImportApi.reconstruct(projectId, pythonCode ?? '', credentialId),
    onSuccess: (data) => {
      setResult(data)
      setEditableName(data.name)
      setStep('preview')
      setError(null)
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Failed to reconstruct workflow')
      setStep('pick')
    },
  })

  const importMutation = useMutation({
    mutationFn: () => {
      if (!result) return Promise.reject(new Error('Nothing to import'))
      return workflowsApi.import(projectId, editableName.trim() || result.name, result.nodes, result.edges, selectedFolderId)
    },
    onSuccess: (workflow) => {
      queryClient.invalidateQueries({ queryKey: ['workflows', projectId] })
      navigate(`/projects/${projectId}/workflows/${workflow.id}`)
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Failed to create workflow')
    },
  })

  async function handleFile(file: File) {
    setFileName(file.name)
    setPythonCode(await file.text())
  }

  function handleGenerate() {
    setError(null)
    setStep('loading')
    reconstructMutation.mutate()
  }

  return (
    <>
      <div className="modal-overlay" onClick={step === 'loading' ? undefined : onClose}>
        <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 520 }}>
          <h3>Import Python (AI)</h3>

          {step === 'pick' && (
            <>
              <p style={{ color: 'var(--text-muted)', fontSize: 12, margin: '0 0 10px' }}>
                Upload an existing Python automation script — an AI reads it and reconstructs it as a workflow
                here, reusing this app's node types wherever it can. Anything it can't map becomes a "?"
                placeholder that still runs the original code as-is.
              </p>

              <div className="field">
                <label>AI Credential</label>
                {eligibleCredentials.length === 0 ? (
                  <div className="hint">
                    No OpenAI or Anthropic credential yet.{' '}
                    <button type="button" className="btn btn-sm" onClick={() => setShowCredentials(true)}>
                      Add one
                    </button>
                  </div>
                ) : (
                  <select value={credentialId} onChange={(e) => setCredentialId(e.target.value)}>
                    <option value="">Select a credential…</option>
                    {eligibleCredentials.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.type})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className="field">
                <label>Python File</label>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <button type="button" className="btn btn-sm" onClick={() => fileInputRef.current?.click()}>
                    Choose file
                  </button>
                  <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{fileName || 'No file chosen'}</span>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".py"
                  style={{ display: 'none' }}
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) handleFile(file)
                    e.target.value = ''
                  }}
                />
              </div>

              {error && <div className="error-banner">{error}</div>}

              <div className="modal-actions">
                <button className="btn" onClick={onClose}>
                  Cancel
                </button>
                <button className="btn btn-primary" disabled={!credentialId || !pythonCode} onClick={handleGenerate}>
                  Generate Workflow
                </button>
              </div>
            </>
          )}

          {step === 'loading' && (
            <div style={{ padding: '30px 0', textAlign: 'center' }}>
              <p style={{ fontSize: 14 }}>Reading your script and mapping it to workflow nodes…</p>
              <p className="hint">This can take up to a minute.</p>
            </div>
          )}

          {step === 'preview' && result && (
            <>
              <div className="field">
                <label>Workflow Name</label>
                <input value={editableName} onChange={(e) => setEditableName(e.target.value)} />
              </div>

              <div className="field">
                <label>Folder</label>
                <select value={selectedFolderId ?? ''} onChange={(e) => setSelectedFolderId(e.target.value || null)}>
                  <option value="">(root)</option>
                  {flatFolders.map(({ folder, depth }) => (
                    <option key={folder.id} value={folder.id}>
                      {'  '.repeat(depth)}
                      {folder.name}
                    </option>
                  ))}
                </select>
              </div>

              <p style={{ fontSize: 13 }}>
                <strong>{result.nodes.length}</strong> node{result.nodes.length === 1 ? '' : 's'} reconstructed
                {result.unknownCount > 0 && (
                  <span style={{ color: 'var(--danger)' }}>
                    {' '}
                    — <strong>{result.unknownCount}</strong> left as "?" placeholders (still runs the original
                    code)
                  </span>
                )}
                .
              </p>

              {result.warnings.length > 0 && (
                <div className="hint" style={{ marginBottom: 10 }}>
                  <strong>Notes from the reconstruction:</strong>
                  <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
                    {result.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {error && <div className="error-banner">{error}</div>}

              <div className="modal-actions">
                <button className="btn" onClick={() => setStep('pick')}>
                  Back
                </button>
                <button
                  className="btn btn-primary"
                  disabled={!editableName.trim() || importMutation.isPending}
                  onClick={() => importMutation.mutate()}
                >
                  Create Workflow
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {showCredentials && <CredentialsManager projectId={projectId} onClose={() => setShowCredentials(false)} />}
    </>
  )
}
