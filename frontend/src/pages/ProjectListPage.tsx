import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { projectsApi } from '../api/projects'

export default function ProjectListPage() {
  const queryClient = useQueryClient()
  const [showNew, setShowNew] = useState(false)
  const [name, setName] = useState('')

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
  })

  const createMutation = useMutation({
    mutationFn: (name: string) => projectsApi.create(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setShowNew(false)
      setName('')
    },
  })

  return (
    <div>
      <div className="topbar">
        <h1>Auto-mation</h1>
        <div className="topbar-right">
          <Link to="/backup" className="btn btn-sm">
            Backup
          </Link>
        </div>
      </div>
      <div className="container">
        <div className="page-header">
          <h2>Projects</h2>
          <button className="btn btn-primary" onClick={() => setShowNew(true)}>
            + New Project
          </button>
        </div>

        {isLoading && <p>Loading...</p>}

        {!isLoading && (!projects || projects.length === 0) && (
          <div className="empty-state">No projects yet. Create your first one to get started.</div>
        )}

        <div className="list">
          {projects?.map((p) => (
            <Link key={p.id} to={`/projects/${p.id}`} className="list-item">
              <div>
                <div className="list-item-title">{p.name}</div>
                <div className="list-item-meta">
                  Updated {new Date(p.updatedAt).toLocaleString()}
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {showNew && (
        <div className="modal-overlay" onClick={() => setShowNew(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>New Project</h3>
            <div className="field">
              <label>Name</label>
              <input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Lead Scraper"
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
