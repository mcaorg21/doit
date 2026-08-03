import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from '@xyflow/react'
import { workflowsApi } from '../api/workflows'
import { nodeTypesApi } from '../api/nodeTypes'
import FlowCanvas from '../editor/FlowCanvas'
import NodePalette from '../editor/NodePalette'
import NodeConfigPanel from '../editor/NodeConfigPanel'
import CodePreviewPanel from '../editor/CodePreviewPanel'
import RunPanel from '../editor/RunPanel'
import { toWFEdges, toWFNodes } from '../editor/convert'
import type { FlowEdgeData, FlowNodeData } from '../editor/types'
import type { NodeTypeSpec } from '../types/nodeType'

let nodeIdCounter = 0
function nextNodeId() {
  nodeIdCounter += 1
  return `node_${Date.now()}_${nodeIdCounter}`
}

export default function EditorPage() {
  const { projectId, workflowId } = useParams<{ projectId: string; workflowId: string }>()
  const queryClient = useQueryClient()

  const [nodes, setNodes] = useState<Node<FlowNodeData>[]>([])
  const [edges, setEdges] = useState<Edge<FlowEdgeData>[]>([])
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [dirty, setDirty] = useState(false)
  const [activeTab, setActiveTab] = useState<'code' | 'run'>('code')
  const [loaded, setLoaded] = useState(false)

  type Snapshot = { nodes: Node<FlowNodeData>[]; edges: Edge<FlowEdgeData>[] }
  const nodesRef = useRef(nodes)
  const edgesRef = useRef(edges)
  const historyRef = useRef<Snapshot[]>([])
  const futureRef = useRef<Snapshot[]>([])
  const lastSnapshotAtRef = useRef(0)
  const MAX_HISTORY = 100
  const [canUndo, setCanUndo] = useState(false)
  const [canRedo, setCanRedo] = useState(false)
  const [bottomPanelHeight, setBottomPanelHeight] = useState(220)

  useEffect(() => {
    nodesRef.current = nodes
  }, [nodes])
  useEffect(() => {
    edgesRef.current = edges
  }, [edges])

  const { data: workflow } = useQuery({
    queryKey: ['workflow', projectId, workflowId],
    queryFn: () => workflowsApi.get(projectId!, workflowId!),
    enabled: !!projectId && !!workflowId,
  })

  const { data: nodeTypes } = useQuery({
    queryKey: ['node-types'],
    queryFn: nodeTypesApi.list,
  })

  const nodeTypesByType = useMemo(() => {
    const map = new Map<string, NodeTypeSpec>()
    for (const spec of nodeTypes ?? []) map.set(spec.type, spec)
    return map
  }, [nodeTypes])

  useEffect(() => {
    if (workflow && !loaded) {
      setName(workflow.name)
      setNodes(
        workflow.nodes.map((n) => ({
          id: n.id,
          type: 'generic',
          position: n.position,
          data: {
            nodeType: n.type,
            label: nodeTypesByType.get(n.type)?.label ?? n.type,
            params: n.params,
            isBranch: nodeTypesByType.get(n.type)?.isBranch ?? false,
            icon: nodeTypesByType.get(n.type)?.icon ?? null,
            title: n.title ?? undefined,
            note: n.note ?? undefined,
          },
        })),
      )
      setEdges(
        workflow.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle ?? undefined,
          type: 'breakpoint',
          data: { breakpoint: e.breakpoint ?? false },
        })),
      )
      setLoaded(true)
    }
  }, [workflow, loaded, nodeTypesByType])

  const saveMutation = useMutation({
    mutationFn: () => workflowsApi.save(projectId!, workflowId!, name, toWFNodes(nodes), toWFEdges(edges)),
    onSuccess: () => {
      setDirty(false)
      queryClient.invalidateQueries({ queryKey: ['workflows', projectId] })
    },
  })

  function markDirty() {
    setDirty(true)
  }

  // Autosave: once the workflow is loaded, any pending edit gets written a couple
  // seconds after the user stops touching the graph — the debounce is what keeps this
  // from firing on every keystroke/drag frame instead of once per pause.
  useEffect(() => {
    if (!loaded || !dirty) return
    const timer = setTimeout(() => {
      saveMutation.mutate()
    }, 2000)
    return () => clearTimeout(timer)
  }, [nodes, edges, name, dirty, loaded])

  // Snapshots the current graph onto the undo stack *before* a mutation is applied.
  // Discrete actions (add/delete/connect) always get their own snapshot; continuous
  // ones (dragging a node, typing in a param field) are debounced so undo doesn't
  // step through every pixel/keystroke.
  function recordHistory(force: boolean) {
    const now = Date.now()
    if (!force && now - lastSnapshotAtRef.current < 600) return
    lastSnapshotAtRef.current = now
    historyRef.current.push({ nodes: nodesRef.current, edges: edgesRef.current })
    if (historyRef.current.length > MAX_HISTORY) historyRef.current.shift()
    futureRef.current = []
    setCanUndo(true)
    setCanRedo(false)
  }

  function undo() {
    const prev = historyRef.current.pop()
    if (!prev) return
    futureRef.current.push({ nodes: nodesRef.current, edges: edgesRef.current })
    setNodes(prev.nodes)
    setEdges(prev.edges)
    setSelectedNodeId(null)
    setDirty(true)
    setCanUndo(historyRef.current.length > 0)
    setCanRedo(true)
  }

  function redo() {
    const next = futureRef.current.pop()
    if (!next) return
    historyRef.current.push({ nodes: nodesRef.current, edges: edgesRef.current })
    setNodes(next.nodes)
    setEdges(next.edges)
    setSelectedNodeId(null)
    setDirty(true)
    setCanRedo(futureRef.current.length > 0)
    setCanUndo(true)
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null
      const isEditableField =
        !!target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
      if (isEditableField) return

      const key = e.key.toLowerCase()
      if ((e.ctrlKey || e.metaKey) && key === 'z' && !e.shiftKey) {
        e.preventDefault()
        undo()
      } else if ((e.ctrlKey || e.metaKey) && (key === 'y' || (key === 'z' && e.shiftKey))) {
        e.preventDefault()
        redo()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  function handleNodesChange(changes: NodeChange<Node<FlowNodeData>>[]) {
    const isStructural = changes.some((c) => c.type === 'remove' || c.type === 'add')
    recordHistory(isStructural)
    setNodes((prev) => applyNodeChanges(changes, prev))
    // React Flow fires internal "dimensions"/"select" changes on render and click;
    // only real edits (add/remove/move) should mark the workflow as unsaved.
    if (changes.some((c) => c.type !== 'dimensions' && c.type !== 'select')) {
      markDirty()
    }
  }

  function handleEdgesChange(changes: EdgeChange[]) {
    const isStructural = changes.some((c) => c.type === 'remove' || c.type === 'add')
    recordHistory(isStructural)
    setEdges((prev) => applyEdgeChanges(changes, prev))
    markDirty()
  }

  function handleConnect(connection: Connection) {
    recordHistory(true)
    setEdges((prev) =>
      addEdge({ ...connection, id: `e_${nextNodeId()}`, type: 'breakpoint', data: { breakpoint: false } }, prev),
    )
    markDirty()
  }

  function handleToggleBreakpoint(edgeId: string) {
    recordHistory(true)
    setEdges((prev) =>
      prev.map((e) => (e.id === edgeId ? { ...e, data: { ...e.data, breakpoint: !e.data?.breakpoint } } : e)),
    )
    markDirty()
  }

  function handleDeleteEdge(edgeId: string) {
    recordHistory(true)
    setEdges((prev) => prev.filter((e) => e.id !== edgeId))
    markDirty()
  }

  function handleAddNode(spec: NodeTypeSpec, position?: { x: number; y: number }) {
    recordHistory(true)
    const params: Record<string, unknown> = {}
    for (const p of spec.params) params[p.key] = p.default
    // Click-to-add (no drop position) lands in a loose grid instead of stacking every
    // new node exactly on top of the last one.
    const resolvedPosition =
      position ?? { x: 120 + (nodes.length % 4) * 180, y: 120 + Math.floor(nodes.length / 4) * 160 }
    const newNode: Node<FlowNodeData> = {
      id: nextNodeId(),
      type: 'generic',
      position: resolvedPosition,
      data: { nodeType: spec.type, label: spec.label, params, isBranch: spec.isBranch, icon: spec.icon },
    }
    setNodes((prev) => [...prev, newNode])
    markDirty()
  }

  function handleChangeParam(key: string, value: unknown) {
    if (!selectedNodeId) return
    recordHistory(false)
    setNodes((prev) =>
      prev.map((n) =>
        n.id === selectedNodeId ? { ...n, data: { ...n.data, params: { ...n.data.params, [key]: value } } } : n,
      ),
    )
    markDirty()
  }

  function handleDeleteNodeById(nodeId: string) {
    recordHistory(true)
    setNodes((prev) => prev.filter((n) => n.id !== nodeId))
    setEdges((prev) => prev.filter((e) => e.source !== nodeId && e.target !== nodeId))
    setSelectedNodeId((current) => (current === nodeId ? null : current))
    markDirty()
  }

  function handleDeleteNode() {
    if (!selectedNodeId) return
    handleDeleteNodeById(selectedNodeId)
  }

  function handleChangeNodeMeta(key: 'title' | 'note', value: string) {
    if (!selectedNodeId) return
    recordHistory(false)
    setNodes((prev) =>
      prev.map((n) => (n.id === selectedNodeId ? { ...n, data: { ...n.data, [key]: value } } : n)),
    )
    markDirty()
  }

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null
  const selectedSpec = selectedNode ? nodeTypesByType.get(selectedNode.data.nodeType) : undefined

  function handleResizeStart(e: React.MouseEvent) {
    e.preventDefault()
    const startY = e.clientY
    const startHeight = bottomPanelHeight

    function onMove(ev: MouseEvent) {
      const delta = startY - ev.clientY
      const next = Math.min(Math.max(startHeight + delta, 100), window.innerHeight - 200)
      setBottomPanelHeight(next)
    }
    function onUp() {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  return (
    <div className="editor-page">
      <div className="topbar">
        <Link to={`/projects/${projectId}`} className="breadcrumb">
          ← Workflows
        </Link>
        <h1>{name || '...'}</h1>
        <div className="spacer" />
        <button className="btn btn-sm" onClick={undo} disabled={!canUndo} title="Undo (Ctrl+Z)">
          ↶ Undo
        </button>
        <button className="btn btn-sm" onClick={redo} disabled={!canRedo} title="Redo (Ctrl+Y)">
          ↷ Redo
        </button>
        {saveMutation.isPending ? (
          <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Saving…</span>
        ) : (
          dirty && <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Unsaved changes</span>
        )}
        <button className="btn" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending || !dirty}>
          Save
        </button>
      </div>

      <div className="editor-body" style={{ gridTemplateRows: `1fr ${bottomPanelHeight}px` }}>
        <NodePalette onAddNode={(spec) => handleAddNode(spec)} />

        <FlowCanvas
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onConnect={handleConnect}
          onSelectNode={setSelectedNodeId}
          onAddNode={handleAddNode}
          onToggleBreakpoint={handleToggleBreakpoint}
          onDeleteEdge={handleDeleteEdge}
          onDeleteNode={handleDeleteNodeById}
          nodeTypesByType={nodeTypesByType}
        />

        <div className="side-panel">
          <NodeConfigPanel
            node={selectedNode}
            spec={selectedSpec}
            onChangeParam={handleChangeParam}
            onChangeMeta={handleChangeNodeMeta}
            onDeleteNode={handleDeleteNode}
          />
        </div>

        <div className="bottom-panel">
          <div className="resize-handle" onMouseDown={handleResizeStart} title="Drag to resize" />
          <div className="panel-tabs">
            <button
              className={`panel-tab ${activeTab === 'code' ? 'active' : ''}`}
              onClick={() => setActiveTab('code')}
            >
              Code Preview
            </button>
            <button className={`panel-tab ${activeTab === 'run' ? 'active' : ''}`} onClick={() => setActiveTab('run')}>
              Run
            </button>
          </div>
          <div className="panel-content">
            {activeTab === 'code' && projectId && workflowId && (
              <CodePreviewPanel projectId={projectId} workflowId={workflowId} nodes={nodes} edges={edges} />
            )}
            {activeTab === 'run' && projectId && workflowId && (
              <RunPanel projectId={projectId} workflowId={workflowId} nodes={nodes} edges={edges} />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
