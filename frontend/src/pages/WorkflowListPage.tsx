import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { projectsApi } from '../api/projects'
import { workflowsApi } from '../api/workflows'
import { foldersApi } from '../api/folders'
import type { Folder, Workflow } from '../types/workflow'

// Flattens the folder tree into a depth-ordered list for the "move to" picker —
// e.g. [{folder: A, depth: 0}, {folder: A/B, depth: 1}, {folder: C, depth: 0}].
function flattenFolders(folders: Folder[], parentId: string | null = null, depth = 0): { folder: Folder; depth: number }[] {
  const children = folders.filter((f) => f.parentId === parentId)
  return children.flatMap((f) => [{ folder: f, depth }, ...flattenFolders(folders, f.id, depth + 1)])
}

export default function WorkflowListPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const currentFolderId = searchParams.get('folder')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [showNewWorkflow, setShowNewWorkflow] = useState(false)
  const [showNewFolder, setShowNewFolder] = useState(false)
  const [name, setName] = useState('')
  const [folderName, setFolderName] = useState('')
  const [projectName, setProjectName] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<Workflow | null>(null)
  const [confirmDeleteFolder, setConfirmDeleteFolder] = useState<Folder | null>(null)
  const [renamingFolder, setRenamingFolder] = useState<Folder | null>(null)
  const [renameFolderValue, setRenameFolderValue] = useState('')
  const [folderError, setFolderError] = useState<string | null>(null)
  const [importError, setImportError] = useState<string | null>(null)

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(projectId!),
    enabled: !!projectId,
  })

  useEffect(() => {
    if (project) setProjectName(project.name)
  }, [project])

  const { data: workflows, isLoading } = useQuery({
    queryKey: ['workflows', projectId],
    queryFn: () => workflowsApi.list(projectId!),
    enabled: !!projectId,
  })

  const { data: folders } = useQuery({
    queryKey: ['folders', projectId],
    queryFn: () => foldersApi.list(projectId!),
    enabled: !!projectId,
  })

  const breadcrumbTrail = useMemo(() => {
    if (!folders) return []
    const byId = new Map(folders.map((f) => [f.id, f]))
    const trail: Folder[] = []
    let cursor = currentFolderId ? byId.get(currentFolderId) : undefined
    while (cursor) {
      trail.unshift(cursor)
      cursor = cursor.parentId ? byId.get(cursor.parentId) : undefined
    }
    return trail
  }, [folders, currentFolderId])

  const childFolders = folders?.filter((f) => f.parentId === currentFolderId) ?? []
  const childWorkflows = workflows?.filter((w) => w.folderId === currentFolderId) ?? []
  const flatFolders = useMemo(() => flattenFolders(folders ?? []), [folders])

  const createMutation = useMutation({
    mutationFn: (name: string) => workflowsApi.create(projectId!, name, currentFolderId),
    onSuccess: (workflow) => {
      queryClient.invalidateQueries({ queryKey: ['workflows', projectId] })
      navigate(`/projects/${projectId}/workflows/${workflow.id}`)
    },
  })

  const createFolderMutation = useMutation({
    mutationFn: (name: string) => foldersApi.create(projectId!, name, currentFolderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folders', projectId] })
      setShowNewFolder(false)
      setFolderName('')
    },
  })

  const renameProjectMutation = useMutation({
    mutationFn: (newName: string) => projectsApi.rename(projectId!, newName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  function commitProjectRename() {
    const trimmed = projectName.trim()
    if (!trimmed || trimmed === project?.name) {
      setProjectName(project?.name ?? '')
      return
    }
    renameProjectMutation.mutate(trimmed)
  }

  const renameFolderMutation = useMutation({
    mutationFn: ({ folderId, name }: { folderId: string; name: string }) => foldersApi.rename(projectId!, folderId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folders', projectId] })
      setRenamingFolder(null)
    },
  })

  const deleteFolderMutation = useMutation({
    mutationFn: (folderId: string) => foldersApi.remove(projectId!, folderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['folders', projectId] })
      setConfirmDeleteFolder(null)
      setFolderError(null)
    },
    onError: (err: unknown) => {
      setFolderError(err instanceof Error ? err.message : 'Failed to delete folder')
    },
  })

  const duplicateMutation = useMutation({
    mutationFn: (workflowId: string) => workflowsApi.duplicate(projectId!, workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows', projectId] })
    },
  })

  const moveMutation = useMutation({
    mutationFn: ({ workflowId, folderId }: { workflowId: string; folderId: string | null }) =>
      workflowsApi.move(projectId!, workflowId, folderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows', projectId] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (workflowId: string) => workflowsApi.remove(projectId!, workflowId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows', projectId] })
      setConfirmDelete(null)
    },
  })

  const importMutation = useMutation({
    mutationFn: (payload: { name: string; nodes: Workflow['nodes']; edges: Workflow['edges'] }) =>
      workflowsApi.import(projectId!, payload.name, payload.nodes, payload.edges, currentFolderId),
    onSuccess: (workflow) => {
      queryClient.invalidateQueries({ queryKey: ['workflows', projectId] })
      navigate(`/projects/${projectId}/workflows/${workflow.id}`)
    },
    onError: (err: unknown) => {
      setImportError(err instanceof Error ? err.message : 'Failed to import workflow')
    },
  })

  async function handleImportFile(file: File) {
    setImportError(null)
    try {
      const parsed = JSON.parse(await file.text())
      if (!Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) {
        throw new Error('Not a valid workflow export — missing nodes/edges')
      }
      importMutation.mutate({
        name: typeof parsed.name === 'string' && parsed.name.trim() ? parsed.name : file.name.replace(/\.json$/i, ''),
        nodes: parsed.nodes,
        edges: parsed.edges,
      })
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Failed to read file')
    }
  }

  function goToFolder(folderId: string | null) {
    if (folderId) setSearchParams({ folder: folderId })
    else setSearchParams({})
  }

  return (
    <div>
      <div className="topbar">
        <Link to="/" className="breadcrumb">
          ← Projects
        </Link>
        <input
          className="topbar-title-input"
          value={projectName}
          placeholder="Project name"
          onChange={(e) => setProjectName(e.target.value)}
          onBlur={commitProjectRename}
          onKeyDown={(e) => {
            if (e.key === 'Enter') e.currentTarget.blur()
          }}
          size={Math.max(8, projectName.length)}
        />
      </div>
      <div className="container">
        <div className="page-header" style={{ flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14 }}>
            <span
              onClick={() => goToFolder(null)}
              style={{ cursor: 'pointer', color: currentFolderId ? 'var(--text-muted)' : undefined, fontWeight: currentFolderId ? 400 : 600 }}
            >
              Workflows
            </span>
            {breadcrumbTrail.map((f, i) => (
              <span key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: 'var(--text-muted)' }}>/</span>
                <span
                  onClick={() => goToFolder(f.id)}
                  style={{
                    cursor: 'pointer',
                    color: i === breadcrumbTrail.length - 1 ? undefined : 'var(--text-muted)',
                    fontWeight: i === breadcrumbTrail.length - 1 ? 600 : 400,
                  }}
                >
                  {f.name}
                </span>
              </span>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-sm" onClick={() => fileInputRef.current?.click()}>
              Import
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="application/json"
              style={{ display: 'none' }}
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) handleImportFile(file)
                e.target.value = ''
              }}
            />
            <button className="btn btn-sm" onClick={() => setShowNewFolder(true)}>
              + New Folder
            </button>
            <button className="btn btn-primary" onClick={() => setShowNewWorkflow(true)}>
              + New Workflow
            </button>
          </div>
        </div>

        {importError && (
          <div className="error-banner" style={{ marginBottom: 12 }}>
            {importError}
          </div>
        )}
        {folderError && (
          <div className="error-banner" style={{ marginBottom: 12 }}>
            {folderError}
          </div>
        )}

        {isLoading && <p>Loading...</p>}

        {!isLoading && childFolders.length === 0 && childWorkflows.length === 0 && (
          <div className="empty-state">
            {currentFolderId ? 'This folder is empty.' : 'No workflows yet in this project.'}
          </div>
        )}

        <div className="list">
          {childFolders.map((f) => (
            <div key={f.id} className="list-item" style={{ cursor: 'pointer' }} onClick={() => goToFolder(f.id)}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--text-muted)', flexShrink: 0 }}>
                  <path d="M4 4h5l2 2h9a1 1 0 0 1 1 1v11a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />
                </svg>
                <div className="list-item-title">{f.name}</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <button
                  className="icon-btn"
                  title="Rename folder"
                  onClick={(e) => {
                    e.stopPropagation()
                    setRenamingFolder(f)
                    setRenameFolderValue(f.name)
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 20h9" />
                    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" />
                  </svg>
                </button>
                <button
                  className="icon-btn icon-btn-danger"
                  title="Delete folder"
                  onClick={(e) => {
                    e.stopPropagation()
                    setFolderError(null)
                    setConfirmDeleteFolder(f)
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                  </svg>
                </button>
              </div>
            </div>
          ))}

          {childWorkflows.map((w) => (
            <Link key={w.id} to={`/projects/${projectId}/workflows/${w.id}`} className="list-item">
              <div>
                <div className="list-item-title">{w.name}</div>
                <div className="list-item-meta">
                  {w.nodes.length} node{w.nodes.length === 1 ? '' : 's'} · Updated{' '}
                  {new Date(w.updatedAt).toLocaleString()}
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span
                  title={w.published ? 'Published' : 'Not published'}
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: w.published ? 'var(--success)' : 'var(--text-muted)',
                    flexShrink: 0,
                  }}
                />
                {flatFolders.length > 0 && (
                  <select
                    value={w.folderId ?? ''}
                    title="Move to folder"
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => {
                      moveMutation.mutate({ workflowId: w.id, folderId: e.target.value || null })
                    }}
                    style={{ fontSize: 12, padding: '2px 4px', maxWidth: 120 }}
                  >
                    <option value="">(root)</option>
                    {flatFolders.map(({ folder, depth }) => (
                      <option key={folder.id} value={folder.id}>
                        {'  '.repeat(depth)}
                        {folder.name}
                      </option>
                    ))}
                  </select>
                )}
                <button
                  className="icon-btn"
                  title="Duplicate workflow"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    duplicateMutation.mutate(w.id)
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                  </svg>
                </button>
                <button
                  className="icon-btn icon-btn-danger"
                  title="Delete workflow"
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setConfirmDelete(w)
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    <line x1="10" y1="11" x2="10" y2="17" />
                    <line x1="14" y1="11" x2="14" y2="17" />
                  </svg>
                </button>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {showNewWorkflow && (
        <div className="modal-overlay" onClick={() => setShowNewWorkflow(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>New Workflow</h3>
            <div className="field">
              <label>Name</label>
              <input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Fill signup form per lead"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && name.trim()) createMutation.mutate(name.trim())
                }}
              />
            </div>
            <div className="modal-actions">
              <button className="btn" onClick={() => setShowNewWorkflow(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={!name.trim() || createMutation.isPending}
                onClick={() => createMutation.mutate(name.trim())}
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {showNewFolder && (
        <div className="modal-overlay" onClick={() => setShowNewFolder(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>New Folder</h3>
            <div className="field">
              <label>Name</label>
              <input
                autoFocus
                value={folderName}
                onChange={(e) => setFolderName(e.target.value)}
                placeholder="e.g. Marketing"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && folderName.trim()) createFolderMutation.mutate(folderName.trim())
                }}
              />
            </div>
            <div className="modal-actions">
              <button className="btn" onClick={() => setShowNewFolder(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={!folderName.trim() || createFolderMutation.isPending}
                onClick={() => createFolderMutation.mutate(folderName.trim())}
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {renamingFolder && (
        <div className="modal-overlay" onClick={() => setRenamingFolder(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Rename Folder</h3>
            <div className="field">
              <label>Name</label>
              <input
                autoFocus
                value={renameFolderValue}
                onChange={(e) => setRenameFolderValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && renameFolderValue.trim()) {
                    renameFolderMutation.mutate({ folderId: renamingFolder.id, name: renameFolderValue.trim() })
                  }
                }}
              />
            </div>
            <div className="modal-actions">
              <button className="btn" onClick={() => setRenamingFolder(null)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={!renameFolderValue.trim() || renameFolderMutation.isPending}
                onClick={() => renameFolderMutation.mutate({ folderId: renamingFolder.id, name: renameFolderValue.trim() })}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmDeleteFolder && (
        <div className="modal-overlay" onClick={() => setConfirmDeleteFolder(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Delete folder</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
              Delete "{confirmDeleteFolder.name}"? It must be empty first.
            </p>
            <div className="modal-actions">
              <button className="btn" onClick={() => setConfirmDeleteFolder(null)}>
                Cancel
              </button>
              <button
                className="btn btn-danger"
                disabled={deleteFolderMutation.isPending}
                onClick={() => deleteFolderMutation.mutate(confirmDeleteFolder.id)}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmDelete && (
        <div className="modal-overlay" onClick={() => setConfirmDelete(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Delete workflow</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
              Delete "{confirmDelete.name}"? This can't be undone.
            </p>
            <div className="modal-actions">
              <button className="btn" onClick={() => setConfirmDelete(null)}>
                Cancel
              </button>
              <button
                className="btn btn-danger"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate(confirmDelete.id)}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
