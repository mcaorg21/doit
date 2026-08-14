import { useQuery } from '@tanstack/react-query'
import { Highlight, themes } from 'prism-react-renderer'
import type { Edge, Node } from '@xyflow/react'
import { workflowsApi } from '../api/workflows'
import { toWFEdges, toWFNodes } from './convert'
import { useDebouncedValue } from './useDebouncedValue'
import type { FlowNodeData } from './types'
import { ApiError } from '../api/client'

interface Props {
  projectId: string
  workflowId: string
  nodes: Node<FlowNodeData>[]
  edges: Edge[]
  startNodeId: string | null
}

export default function CodePreviewPanel({ projectId, workflowId, nodes, edges, startNodeId }: Props) {
  const debouncedNodes = useDebouncedValue(nodes, 400)
  const debouncedEdges = useDebouncedValue(edges, 400)

  const wfNodes = toWFNodes(debouncedNodes)
  const wfEdges = toWFEdges(debouncedEdges)

  const { data, error } = useQuery({
    queryKey: ['generate-code', projectId, workflowId, wfNodes, wfEdges, startNodeId],
    queryFn: () => workflowsApi.generateCode(projectId, workflowId, wfNodes, wfEdges, startNodeId),
    enabled: wfNodes.length > 0,
    retry: false,
  })

  if (wfNodes.length === 0) {
    return <div className="node-config-empty">Add nodes to the canvas to see the generated Python code.</div>
  }

  if (error) {
    const message = error instanceof ApiError ? error.message : 'Failed to generate code'
    return <div className="error-banner">{message}</div>
  }

  return (
    <Highlight theme={themes.nightOwl} code={data?.code ?? ''} language="python">
      {({ style, tokens, getLineProps, getTokenProps }) => (
        <pre style={{ ...style, margin: 0, background: 'transparent' }}>
          {tokens.map((line, i) => (
            <div key={i} {...getLineProps({ line })}>
              {line.map((token, key) => (
                <span key={key} {...getTokenProps({ token })} />
              ))}
            </div>
          ))}
        </pre>
      )}
    </Highlight>
  )
}
