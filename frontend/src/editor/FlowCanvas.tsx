import { forwardRef, useCallback, useImperativeHandle, useMemo, useRef, useState } from 'react'
import {
  Background,
  ControlButton,
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
  onSelectNode: (nodeId: string | null, event?: React.MouseEvent) => void
  onAddNode: (spec: NodeTypeSpec, position: { x: number; y: number }) => void
  onToggleBreakpoint: (edgeId: string) => void
  onDeleteEdge: (edgeId: string) => void
  onDeleteNode: (nodeId: string) => void
  onDuplicateNode: (nodeId: string) => void
  onRunNodePreview: (nodeId: string) => Promise<unknown>
  onSaveFieldMap: (nodeId: string, fieldMap: string[]) => void
  nodeTypesByType: Map<string, NodeTypeSpec>
  startNodeId: string | null
  onSetStartNode: (nodeId: string) => void
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
    onSaveFieldMap,
    nodeTypesByType,
    startNodeId,
    onSetStartNode,
  }: Props,
  ref: React.ForwardedRef<FlowCanvasHandle>,
) {
  const wrapperRef = useRef<HTMLDivElement>(null)
  const { screenToFlowPosition } = useReactFlow()
  // Default is "hand" mode (dragging empty canvas pans it, like every other screen
  // in this app). Toggling this to "select" mode swaps that: dragging the canvas
  // now draws a rectangle that multi-selects whatever nodes it touches, and Delete
  // removes all of them at once — the complement to Ctrl/Shift+click for picking up
  // several nodes without needing to click each one individually.
  const [selectMode, setSelectMode] = useState(false)

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
        <GenericNode
          {...props}
          isStartNode={props.id === startNodeId}
          onDelete={onDeleteNode}
          onDuplicate={onDuplicateNode}
          onSetStartNode={onSetStartNode}
          onRunPreview={onRunNodePreview}
          onSaveFieldMap={onSaveFieldMap}
        />
      ),
    }),
    [onDeleteNode, onDuplicateNode, onSetStartNode, onRunNodePreview, onSaveFieldMap, startNodeId],
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
    <div
      className={`canvas-wrap${selectMode ? ' canvas-select-mode' : ''}`}
      ref={wrapperRef}
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypeComponents}
        edgeTypes={edgeTypeComponents}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(event, node) => onSelectNode(node.id, event)}
        onPaneClick={() => onSelectNode(null)}
        panOnDrag={!selectMode}
        selectionOnDrag={selectMode}
        fitView
      >
        <Background />
        <Controls>
          <ControlButton
            className={selectMode ? 'control-button-active' : undefined}
            onClick={() => setSelectMode((v) => !v)}
            title={
              selectMode
                ? 'Modo de seleção (arraste pra marcar vários nodes) — clique pra voltar a arrastar o canvas'
                : 'Modo de navegação (arraste move o canvas) — clique pra arrastar e marcar vários nodes de uma vez'
            }
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m3 3 7.07 16.97 2.51-7.39 7.39-2.51L3 3z" />
            </svg>
          </ControlButton>
        </Controls>
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
