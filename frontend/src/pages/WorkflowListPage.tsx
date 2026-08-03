import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { projectsApi } from '../api/projects'
import { workflowsApi } from '../api/workflows'

export default function WorkflowListPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showNew, setShowNew] = useState(false)
  const [name, setName] = useState('')

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(projectId!),
    enabled: !!projectId,
  })

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

  return (
    <div>
      <div className="topbar">
        <Link to="/" className="breadcrumb">
          ← Projects
        </Link>
        <h1>{project?.name ?? '...'}</h1>
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
    </div>
  )
}
