import { useCallback, useMemo, useRef } from 'react'
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Connection,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeChange,
  type EdgeChange,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import GenericNode from './nodes/GenericNode'
import BreakpointEdge from './edges/BreakpointEdge'
import type { FlowEdgeData, FlowNodeData } from './types'
import type { NodeTypeSpec } from '../types/nodeType'

interface Props {
  nodes: Node<FlowNodeData>[]
  edges: Edge<FlowEdgeData>[]
  onNodesChange: (changes: NodeChange<Node<FlowNodeData>>[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onConnect: (connection: Connection) => void
  onSelectNode: (nodeId: string | null) => void
  onAddNode: (spec: NodeTypeSpec, position: { x: number; y: number }) => void
  onToggleBreakpoint: (edgeId: string) => void
  onDeleteNode: (nodeId: string) => void
  nodeTypesByType: Map<string, NodeTypeSpec>
}

function FlowCanvasInner({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onSelectNode,
  onAddNode,
  onToggleBreakpoint,
  onDeleteNode,
  nodeTypesByType,
}: Props) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const { screenToFlowPosition } = useReactFlow()

  const edgeTypeComponents = useMemo(
    () => ({
      breakpoint: (props: EdgeProps) => <BreakpointEdge {...props} onToggle={onToggleBreakpoint} />,
    }),
    [onToggleBreakpoint],
  )

  const nodeTypeComponents = useMemo(
    () => ({
      generic: (props: NodeProps & { data: FlowNodeData }) => <GenericNode {...props} onDelete={onDeleteNode} />,
    }),
    [onDeleteNode],
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      const nodeType = e.dataTransfer.getData('application/x-automation-node-type')
      const spec = nodeTypesByType.get(nodeType)
      if (!spec) return
      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY })
      onAddNode(spec, position)
    },
    [nodeTypesByType, onAddNode, screenToFlowPosition],
  )

  return (
    <div className="canvas-wrap" ref={wrapperRef} onDrop={handleDrop} onDragOver={(e) => e.preventDefault()}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypeComponents}
        edgeTypes={edgeTypeComponents}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_, node) => onSelectNode(node.id)}
        onPaneClick={() => onSelectNode(null)}
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  )
}

export default function FlowCanvas(props: Props) {
  return (
    <ReactFlowProvider>
      <FlowCanvasInner {...props} />
    </ReactFlowProvider>
  )
}
