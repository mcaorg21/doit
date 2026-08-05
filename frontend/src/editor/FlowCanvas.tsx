import { forwardRef, useCallback, useImperativeHandle, useMemo, useRef } from 'react'
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

export interface FlowCanvasHandle {
  /** Flow-space coordinates of the center of the currently visible canvas area —
   * used to drop click-to-add nodes where the user is actually looking instead of a
   * viewport-independent grid that can land far outside the current pan/zoom. */
  getViewportCenterPosition: () => { x: number; y: number }
}

interface Props {
  nodes: Node<FlowNodeData>[]
  edges: Edge<FlowEdgeData>[]
  onNodesChange: (changes: NodeChange<Node<FlowNodeData>>[]) => void
  onEdgesChange: (changes: EdgeChange[]) => void
  onConnect: (connection: Connection) => void
  onSelectNode: (nodeId: string | null) => void
  onAddNode: (spec: NodeTypeSpec, position: { x: number; y: number }) => void
  onToggleBreakpoint: (edgeId: string) => void
  onDeleteEdge: (edgeId: string) => void
  onDeleteNode: (nodeId: string) => void
  onDuplicateNode: (nodeId: string) => void
  onRunNodePreview: (nodeId: string) => Promise<unknown>
  nodeTypesByType: Map<string, NodeTypeSpec>
}

function FlowCanvasInner(
  {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    onSelectNode,
    onAddNode,
    onToggleBreakpoint,
    onDeleteEdge,
    onDeleteNode,
    onDuplicateNode,
    onRunNodePreview,
    nodeTypesByType,
  }: Props,
  ref: React.ForwardedRef<FlowCanvasHandle>,
) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const { screenToFlowPosition } = useReactFlow()

  useImperativeHandle(
    ref,
    () => ({
      getViewportCenterPosition: () => {
        const rect = wrapperRef.current?.getBoundingClientRect()
        if (!rect) return { x: 0, y: 0 }
        return screenToFlowPosition({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 })
      },
    }),
    [screenToFlowPosition],
  )

  const edgeTypeComponents = useMemo(
    () => ({
      breakpoint: (props: EdgeProps) => (
        <BreakpointEdge {...props} onToggle={onToggleBreakpoint} onDelete={onDeleteEdge} />
      ),
    }),
    [onToggleBreakpoint, onDeleteEdge],
  )

  const nodeTypeComponents = useMemo(
    () => ({
      generic: (props: NodeProps & { data: FlowNodeData }) => (
        <GenericNode {...props} onDelete={onDeleteNode} onDuplicate={onDuplicateNode} onRunPreview={onRunNodePreview} />
      ),
    }),
    [onDeleteNode, onDuplicateNode, onRunNodePreview],
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

const FlowCanvasInnerWithRef = forwardRef(FlowCanvasInner)

const FlowCanvas = forwardRef<FlowCanvasHandle, Props>((props, ref) => (
  <ReactFlowProvider>
    <FlowCanvasInnerWithRef {...props} ref={ref} />
  </ReactFlowProvider>
))

export default FlowCanvas
