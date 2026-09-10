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

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
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
