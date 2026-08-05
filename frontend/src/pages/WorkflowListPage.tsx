import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { projectsApi } from '../api/projects'
import { workflowsApi } from '../api/workflows'
import type { Workflow } from '../types/workflow'

export default function WorkflowListPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showNew, setShowNew] = useState(false)
  const [name, setName] = useState('')
  const [projectName, setProjectName] = useState('')
  const [confirmDelete, setConfirmDelete] = useState<Workflow | null>(null)

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

  const createMutation = useMutation({
    mutationFn: (name: string) => workflowsApi.create(projectId!, name),
    onSuccess: (workflow) => {
      queryClient.invalidateQueries({ queryKey: ['workflows', projectId] })
      navigate(`/projects/${projectId}/workflows/${workflow.id}`)
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

  const duplicateMutation = useMutation({
    mutationFn: (workflowId: string) => workflowsApi.duplicate(projectId!, workflowId),
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
        <div className="page-header">
          <h2>Workflows</h2>
          <button className="btn btn-primary" onClick={() => setShowNew(true)}>
            + New Workflow
          </button>
        </div>

        {isLoading && <p>Loading...</p>}

        {!isLoading && (!workflows || workflows.length === 0) && (
          <div className="empty-state">No workflows yet in this project.</div>
        )}

        <div className="list">
          {workflows?.map((w) => (
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

      {showNew && (
        <div className="modal-overlay" onClick={() => setShowNew(false)}>
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
              <button className="btn" onClick={() => setShowNew(false)}>
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
