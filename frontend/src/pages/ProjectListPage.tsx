import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { projectsApi } from '../api/projects'
import { backupApi } from '../api/backup'
import { ApiError } from '../api/client'
import type { Project } from '../types/workflow'

export default function ProjectListPage() {
  const queryClient = useQueryClient()
  const [showNew, setShowNew] = useState(false)
  const [name, setName] = useState('')
  const [backupPromptProject, setBackupPromptProject] = useState<Project | null>(null)
  const [connectionString, setConnectionString] = useState('')
  const [backupError, setBackupError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<Project | null>(null)

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => projectsApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setConfirmDelete(null)
    },
  })

  const createMutation = useMutation({
    mutationFn: (name: string) => projectsApi.create(name),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setShowNew(false)
      setName('')
      // Every new project starts with no backup connection configured (it's
      // per-project, see backup_config_store.py) — ask for one right away instead
      // of silently leaving it unprotected until the user thinks to visit /backup.
      setBackupPromptProject(project)
    },
  })

  const saveBackupMutation = useMutation({
    mutationFn: (value: string) => backupApi.saveConfig(backupPromptProject!.id, value),
    onSuccess: () => {
      setBackupPromptProject(null)
      setConnectionString('')
      setBackupError(null)
    },
    onError: (err: unknown) => {
      setBackupError(err instanceof ApiError || err instanceof Error ? err.message : 'Failed to save connection')
    },
  })

  return (
    <div>
      <div className="topbar">
        <h1>Auto-mation</h1>
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
            <div key={p.id} className="list-item">
              <Link to={`/projects/${p.id}`} style={{ display: 'contents', color: 'inherit', textDecoration: 'none' }}>
                <div>
                  <div className="list-item-title">{p.name}</div>
                  <div className="list-item-meta">
                    Updated {new Date(p.updatedAt).toLocaleString()}
                  </div>
                </div>
              </Link>
              {p.workflowCount === 0 && (
                <button
                  className="icon-btn icon-btn-danger"
                  title="Delete empty project"
                  onClick={(e) => {
                    e.preventDefault()
                    setConfirmDelete(p)
                  }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    <line x1="10" y1="11" x2="10" y2="17" />
                    <line x1="14" y1="11" x2="14" y2="17" />
                  </svg>
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {confirmDelete && (
        <div className="modal-overlay" onClick={() => setConfirmDelete(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Delete project</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
              Delete "{confirmDelete.name}"? It has no workflows, so this can't be undone by restoring anything —
              the project itself (and its credentials) will be gone.
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

      {backupPromptProject && (
        <div
          className="modal-overlay"
          onClick={() => {
            setBackupPromptProject(null)
            setConnectionString('')
            setBackupError(null)
          }}
        >
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Configurar backup — {backupPromptProject.name}</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: -6 }}>
              Este projeto ainda não tem um endereço de backup (Postgres) configurado. Você pode configurar agora ou
              pular e fazer isso depois na página de Backup do projeto.
            </p>
            <div className="field">
              <label>Connection string do Postgres</label>
              <input
                autoFocus
                value={connectionString}
                onChange={(e) => setConnectionString(e.target.value)}
                placeholder="postgresql://user:senha@host:5432/dbname"
              />
            </div>
            {backupError && <div className="error-banner">{backupError}</div>}
            <div className="modal-actions">
              <button
                className="btn"
                onClick={() => {
                  setBackupPromptProject(null)
                  setConnectionString('')
                  setBackupError(null)
                }}
              >
                Configurar depois
              </button>
              <button
                className="btn btn-primary"
                disabled={!connectionString.trim() || saveBackupMutation.isPending}
                onClick={() => saveBackupMutation.mutate(connectionString.trim())}
              >
                {saveBackupMutation.isPending ? 'Testando conexão…' : 'Salvar conexão'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
