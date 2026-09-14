import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { projectsApi } from '../api/projects'
import { workflowsApi } from '../api/workflows'
import ExecutionsPanel from '../editor/ExecutionsPanel'

export default function ExecutionsPage() {
  const { projectId } = useParams<{ projectId: string }>()

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(projectId!),
    enabled: !!projectId,
  })

  const { data: workflows } = useQuery({
    queryKey: ['workflows', projectId],
    queryFn: () => workflowsApi.list(projectId!),
    enabled: !!projectId,
  })

  const workflowNames = useMemo(() => {
    const map = new Map<string, string>()
    for (const w of workflows ?? []) map.set(w.id, w.name)
    return map
  }, [workflows])

  return (
    <div>
      <div className="topbar">
        <Link to={`/projects/${projectId}`} viewTransition className="breadcrumb">
          ← {project?.name ?? 'Project'}
        </Link>
      </div>
      <div className="container">
        <div className="page-header">
          <h2>Executions</h2>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: -8, marginBottom: 20 }}>
          Every run of every workflow in this project, most recent first.
        </p>
        {projectId && <ExecutionsPanel projectId={projectId} workflowNames={workflowNames} />}
      </div>
    </div>
  )
}
