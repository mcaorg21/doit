import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { backupApi } from '../api/backup'
import { projectsApi } from '../api/projects'
import { ApiError } from '../api/client'
import type { BackupCounts, RestorePreview } from '../types/workflow'

function formatCounts(counts: BackupCounts) {
  return `${counts.projects} projetos, ${counts.workflows} workflows, ${counts.credentials} credenciais, ${counts.runs} runs`
}

export default function BackupPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const queryClient = useQueryClient()
  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(projectId!),
    enabled: !!projectId,
  })
  const { data: status, isLoading } = useQuery({
    queryKey: ['backup-status', projectId],
    queryFn: () => backupApi.getStatus(projectId!),
    enabled: !!projectId,
  })

  const [connectionString, setConnectionString] = useState('')
  const [revealed, setRevealed] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [restorePreview, setRestorePreview] = useState<RestorePreview | null>(null)
  const [showRemoveConfirm, setShowRemoveConfirm] = useState(false)

  useEffect(() => {
    if (status?.connectionString) setConnectionString(status.connectionString)
  }, [status?.connectionString])

  const saveMutation = useMutation({
    mutationFn: (value: string) => backupApi.saveConfig(projectId!, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backup-status', projectId] })
      setError(null)
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Failed to save connection')
    },
  })

  const backupMutation = useMutation({
    mutationFn: () => backupApi.runBackup(projectId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backup-status', projectId] })
      setError(null)
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Backup failed')
    },
  })

  const previewMutation = useMutation({
    mutationFn: () => backupApi.preview(projectId!),
    onSuccess: (data) => {
      setRestorePreview(data)
      setError(null)
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Failed to read backup contents')
    },
  })

  const restoreMutation = useMutation({
    mutationFn: () => backupApi.restore(projectId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backup-status', projectId] })
      setRestorePreview(null)
      setError(null)
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError || err instanceof Error ? err.message : 'Restore failed')
    },
  })

  const removeMutation = useMutation({
    mutationFn: () => backupApi.removeConfig(projectId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backup-status', projectId] })
      setConnectionString('')
      setShowRemoveConfirm(false)
    },
  })

  const configured = status?.configured ?? false

  return (
    <div>
      <div className="topbar">
        <Link to={`/projects/${projectId}`} className="breadcrumb">
          ← {project?.name ?? 'Projeto'}
        </Link>
      </div>
      <div className="container">
        <div className="page-header">
          <h2>Backup</h2>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: -8, marginBottom: 20 }}>
          Uma conexão Postgres exclusiva deste projeto — usada só como cópia de segurança contra a perda dos
          arquivos locais em <code>data/projects/{projectId}</code>. Nada é enviado automaticamente; o backup só
          roda quando você aperta o botão.
        </p>

        {isLoading && <p>Loading...</p>}

        {!isLoading && (
          <>
            <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <div className="field">
                <label>Connection string do Postgres</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  <input
                    type={revealed ? 'text' : 'password'}
                    value={connectionString}
                    onChange={(e) => setConnectionString(e.target.value)}
                    placeholder="postgresql://user:senha@host:5432/dbname"
                    style={{ flex: 1 }}
                  />
                  <button className="icon-btn" title={revealed ? 'Ocultar' : 'Mostrar'} onClick={() => setRevealed((r) => !r)}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      {revealed ? (
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
                </div>
                <span className="hint">
                  Ao salvar, a conexão é testada e as tabelas (<code>automation_*</code>) são criadas automaticamente
                  se ainda não existirem. Guardado em texto puro localmente, igual às credenciais.
                </span>
              </div>

              {error && <div className="error-banner">{error}</div>}

              <div className="modal-actions" style={{ justifyContent: 'flex-start' }}>
                <button
                  className="btn btn-primary"
                  disabled={!connectionString.trim() || saveMutation.isPending}
                  onClick={() => saveMutation.mutate(connectionString.trim())}
                >
                  {saveMutation.isPending ? 'Testando conexão…' : 'Salvar conexão'}
                </button>
                {configured && (
                  <button className="btn btn-sm" onClick={() => setShowRemoveConfirm(true)}>
                    Remover conexão
                  </button>
                )}
              </div>
            </div>

            <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 16, marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: configured ? 8 : 0 }}>
                <h3 style={{ margin: 0 }}>Status</h3>
                {configured && (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      fontSize: 12,
                      fontWeight: 600,
                      color: 'var(--success)',
                      background: 'color-mix(in srgb, var(--success) 14%, transparent)',
                      border: '1px solid color-mix(in srgb, var(--success) 45%, var(--border))',
                      borderRadius: 999,
                      padding: '2px 10px 2px 8px',
                    }}
                  >
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--success)', flexShrink: 0 }} />
                    Conectado
                  </span>
                )}
              </div>
              {!configured && <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Nenhuma conexão configurada ainda.</p>}
              {configured && (
                <>
                  <p style={{ fontSize: 13 }}>
                    {status?.lastBackupAt ? (
                      <>
                        Último backup: {new Date(status.lastBackupAt).toLocaleString()}
                        {status.lastBackupCounts && <> — {formatCounts(status.lastBackupCounts)}</>}
                      </>
                    ) : (
                      'Nunca fez backup ainda.'
                    )}
                  </p>
                  {status?.lastRestoreAt && (
                    <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                      Última restauração: {new Date(status.lastRestoreAt).toLocaleString()}
                    </p>
                  )}
                  {backupMutation.data?.warnings && backupMutation.data.warnings.length > 0 && (
                    <div className="error-banner">
                      {backupMutation.data.warnings.map((w, i) => (
                        <div key={i}>{w}</div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                className="btn btn-primary"
                disabled={!configured || backupMutation.isPending}
                onClick={() => backupMutation.mutate()}
              >
                {backupMutation.isPending ? 'Fazendo backup…' : 'Fazer Backup Agora'}
              </button>
              <button
                className="btn"
                disabled={!configured || previewMutation.isPending}
                onClick={() => previewMutation.mutate()}
              >
                {previewMutation.isPending ? 'Lendo…' : 'Restaurar do Backup'}
              </button>
            </div>
          </>
        )}
      </div>

      {restorePreview && (
        <div className="modal-overlay" onClick={() => setRestorePreview(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Restaurar do Backup</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
              O Postgres tem: {formatCounts(restorePreview.counts)}.
            </p>
            <p style={{ fontSize: 13, color: 'var(--danger)', fontWeight: 600 }}>
              Isso vai APAGAR os dados locais atuais deste projeto e substituir pelo conteúdo do Postgres. Não pode
              ser desfeito.
            </p>
            <div className="modal-actions">
              <button className="btn" onClick={() => setRestorePreview(null)}>
                Cancelar
              </button>
              <button
                className="btn btn-danger"
                disabled={restoreMutation.isPending}
                onClick={() => restoreMutation.mutate()}
              >
                {restoreMutation.isPending ? 'Restaurando…' : 'Restaurar (apagar dados locais)'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showRemoveConfirm && (
        <div className="modal-overlay" onClick={() => setShowRemoveConfirm(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Remover conexão</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
              Remove só o cadastro local da connection string — não apaga nada no Postgres nem os backups já feitos
              lá.
            </p>
            <div className="modal-actions">
              <button className="btn" onClick={() => setShowRemoveConfirm(false)}>
                Cancelar
              </button>
              <button className="btn btn-danger" disabled={removeMutation.isPending} onClick={() => removeMutation.mutate()}>
                Remover
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
