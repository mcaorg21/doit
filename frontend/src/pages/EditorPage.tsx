import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
import { ApiError } from '../api/client'
import { nodeTypesApi } from '../api/nodeTypes'
import FlowCanvas, { type FlowCanvasHandle } from '../editor/FlowCanvas'
import NodePalette from '../editor/NodePalette'
import NodeConfigPanel from '../editor/NodeConfigPanel'
import CodePreviewPanel from '../editor/CodePreviewPanel'
import RunPanel from '../editor/RunPanel'
import ExecutionsPanel from '../editor/ExecutionsPanel'
import { toWFEdges, toWFNodes } from '../editor/convert'
import { getUpstreamVariables, getUpstreamFieldMapOptions, type VariableSource } from '../editor/graph'
import { genRandomToken } from '../editor/randomToken'
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
  const [startNodeId, setStartNodeId] = useState<string | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [dirty, setDirty] = useState(false)
  const [activeTab, setActiveTab] = useState<'code' | 'run' | 'executions'>('code')
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
  const flowCanvasRef = useRef<FlowCanvasHandle>(null)
  const selectedNodeIdRef = useRef(selectedNodeId)
  const clipboardRef = useRef<Node<FlowNodeData> | null>(null)

  useEffect(() => {
    nodesRef.current = nodes
  }, [nodes])
  useEffect(() => {
    edgesRef.current = edges
  }, [edges])
  useEffect(() => {
    selectedNodeIdRef.current = selectedNodeId
  }, [selectedNodeId])

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
      // Backfills any autoGenerate field (e.g. Webhook's Secret) that's missing a
      // value — covers nodes saved before that field existed, so opening an old
      // workflow doesn't leave it stuck with an empty, unregisterable secret.
      let backfilled = false
      setNodes(
        workflow.nodes.map((n) => {
          const params = { ...n.params }
          for (const p of nodeTypesByType.get(n.type)?.params ?? []) {
            if (p.autoGenerate && !params[p.key]) {
              params[p.key] = genRandomToken()
              backfilled = true
            }
          }
          return {
            id: n.id,
            type: 'generic',
            position: n.position,
            data: {
              nodeType: n.type,
              label: nodeTypesByType.get(n.type)?.label ?? n.type,
              params,
              isBranch: nodeTypesByType.get(n.type)?.isBranch ?? false,
              icon: nodeTypesByType.get(n.type)?.icon ?? null,
              title: n.title ?? undefined,
              note: n.note ?? undefined,
              fieldMap: n.fieldMap ?? undefined,
            },
          }
        }),
      )
      if (backfilled) markDirty()
      setStartNodeId(workflow.startNodeId ?? null)
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
    mutationFn: () =>
      workflowsApi.save(projectId!, workflowId!, name, toWFNodes(nodes), toWFEdges(edges), startNodeId),
    onSuccess: () => {
      setDirty(false)
      queryClient.invalidateQueries({ queryKey: ['workflows', projectId] })
    },
  })

  const markDirty = useCallback(() => setDirty(true), [])

  const [publishError, setPublishError] = useState<string | null>(null)

  const publishMutation = useMutation({
    mutationFn: () => workflowsApi.publish(projectId!, workflowId!),
    onSuccess: (updated) => {
      setPublishError(null)
      queryClient.setQueryData(['workflow', projectId, workflowId], updated)
      queryClient.invalidateQueries({ queryKey: ['workflows', projectId] })
    },
    onError: (err: unknown) => {
      setPublishError(err instanceof ApiError || err instanceof Error ? err.message : 'Failed to publish')
    },
  })

  const unpublishMutation = useMutation({
    mutationFn: () => workflowsApi.unpublish(projectId!, workflowId!),
    onSuccess: (updated) => {
      setPublishError(null)
      queryClient.setQueryData(['workflow', projectId, workflowId], updated)
      queryClient.invalidateQueries({ queryKey: ['workflows', projectId] })
    },
  })

  // Autosave: once the workflow is loaded, any pending edit gets written a couple
  // seconds after the user stops touching the graph — the debounce is what keeps this
  // from firing on every keystroke/drag frame instead of once per pause.
  useEffect(() => {
    if (!loaded || !dirty) return
    const timer = setTimeout(() => {
      saveMutation.mutate()
    }, 2000)
    return () => clearTimeout(timer)
  }, [nodes, edges, name, startNodeId, dirty, loaded])

  // Snapshots the current graph onto the undo stack *before* a mutation is applied.
  // Discrete actions (add/delete/connect) always get their own snapshot; continuous
  // ones (dragging a node, typing in a param field) are debounced so undo doesn't
  // step through every pixel/keystroke.
  const recordHistory = useCallback((force: boolean) => {
    const now = Date.now()
    if (!force && now - lastSnapshotAtRef.current < 600) return
    lastSnapshotAtRef.current = now
    historyRef.current.push({ nodes: nodesRef.current, edges: edgesRef.current })
    if (historyRef.current.length > MAX_HISTORY) historyRef.current.shift()
    futureRef.current = []
    setCanUndo(true)
    setCanRedo(false)
  }, [])

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
        return
      }
      if ((e.ctrlKey || e.metaKey) && (key === 'y' || (key === 'z' && e.shiftKey))) {
        e.preventDefault()
        redo()
        return
      }

      if ((e.ctrlKey || e.metaKey) && key === 'c') {
        const id = selectedNodeIdRef.current
        if (!id) return
        const node = nodesRef.current.find((n) => n.id === id)
        if (!node) return
        e.preventDefault()
        clipboardRef.current = node
        return
      }

      if ((e.ctrlKey || e.metaKey) && key === 'v') {
        const copied = clipboardRef.current
        if (!copied) return
        e.preventDefault()
        recordHistory(true)
        const position = { x: copied.position.x + 36, y: copied.position.y + 36 }
        const newNode: Node<FlowNodeData> = {
          ...copied,
          id: nextNodeId(),
          position,
          selected: false,
          data: { ...copied.data, params: { ...copied.data.params } },
        }
        setNodes((prev) => [...prev, newNode])
        setSelectedNodeId(newNode.id)
        markDirty()
        // Re-anchor the clipboard to the pasted copy so repeated Ctrl+V cascades
        // diagonally (like the Duplicate button) instead of stacking every paste
        // on the exact same spot.
        clipboardRef.current = newNode
        return
      }

      if (key === 'delete' || key === 'backspace') {
        const id = selectedNodeIdRef.current
        if (!id) return
        e.preventDefault()
        handleDeleteNodeById(id)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
    // handleDeleteNodeById isn't declared yet at this point in the component body (it's
    // defined further down), so it can't go in this array — referencing it from inside
    // the closure is still safe since it's only actually called later, well after the
    // whole component function (and that declaration) has run, and its identity is
    // stable across renders anyway (it's memoized with useCallback).
  }, [recordHistory, markDirty])

  const handleNodesChange = useCallback(
    (changes: NodeChange<Node<FlowNodeData>>[]) => {
      const isStructural = changes.some((c) => c.type === 'remove' || c.type === 'add')
      recordHistory(isStructural)
      setNodes((prev) => applyNodeChanges(changes, prev))
      // React Flow fires internal "dimensions"/"select" changes on render and click;
      // only real edits (add/remove/move) should mark the workflow as unsaved.
      if (changes.some((c) => c.type !== 'dimensions' && c.type !== 'select')) {
        markDirty()
      }
    },
    [recordHistory, markDirty],
  )

  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      const isStructural = changes.some((c) => c.type === 'remove' || c.type === 'add')
      recordHistory(isStructural)
      setEdges((prev) => applyEdgeChanges(changes, prev))
      markDirty()
    },
    [recordHistory, markDirty],
  )

  const handleConnect = useCallback(
    (connection: Connection) => {
      recordHistory(true)
      setEdges((prev) =>
        addEdge({ ...connection, id: `e_${nextNodeId()}`, type: 'breakpoint', data: { breakpoint: false } }, prev),
      )
      markDirty()
    },
    [recordHistory, markDirty],
  )

  const handleToggleBreakpoint = useCallback(
    (edgeId: string) => {
      recordHistory(true)
      setEdges((prev) =>
        prev.map((e) => (e.id === edgeId ? { ...e, data: { ...e.data, breakpoint: !e.data?.breakpoint } } : e)),
      )
      markDirty()
    },
    [recordHistory, markDirty],
  )

  const handleDeleteEdge = useCallback(
    (edgeId: string) => {
      recordHistory(true)
      setEdges((prev) => prev.filter((e) => e.id !== edgeId))
      markDirty()
    },
    [recordHistory, markDirty],
  )

  function handleAddNode(spec: NodeTypeSpec, position?: { x: number; y: number }) {
    recordHistory(true)
    const params: Record<string, unknown> = {}
    for (const p of spec.params) params[p.key] = p.autoGenerate ? genRandomToken() : p.default
    // Click-to-add (no drop position) lands at the center of whatever part of the
    // canvas the user is currently looking at, not a viewport-independent grid that
    // can end up far outside the visible pan/zoom. A small cascade (wrapping every 8
    // nodes) keeps repeated clicks from stacking new nodes exactly on top of each other.
    const center = flowCanvasRef.current?.getViewportCenterPosition()
    const cascadeIndex = nodes.length % 8
    const resolvedPosition =
      position ??
      (center
        ? { x: center.x - 28 + cascadeIndex * 28, y: center.y - 28 + cascadeIndex * 28 }
        : { x: 120 + (nodes.length % 6) * 160, y: 120 + Math.floor(nodes.length / 6) * 140 })
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

  const handleDeleteNodeById = useCallback(
    (nodeId: string) => {
      recordHistory(true)
      setNodes((prev) => prev.filter((n) => n.id !== nodeId))
      setEdges((prev) => prev.filter((e) => e.source !== nodeId && e.target !== nodeId))
      setSelectedNodeId((current) => (current === nodeId ? null : current))
      // A deleted Start Node would otherwise leave a dangling reference — harmless to
      // codegen (it just falls back to erroring on ambiguity again like before this
      // node existed), but clearing it here keeps the picked start node always valid.
      setStartNodeId((current) => (current === nodeId ? null : current))
      markDirty()
    },
    [recordHistory, markDirty],
  )

  const handleSetStartNode = useCallback(
    (nodeId: string) => {
      setStartNodeId((current) => (current === nodeId ? null : nodeId))
      markDirty()
    },
    [markDirty],
  )

  function handleDeleteNode() {
    if (!selectedNodeId) return
    handleDeleteNodeById(selectedNodeId)
  }

  const handleDuplicateNode = useCallback(
    (nodeId: string) => {
      const original = nodesRef.current.find((n) => n.id === nodeId)
      if (!original) return
      recordHistory(true)
      const params = { ...original.data.params }
      // Fields like Webhook's Secret must stay unique per node — a duplicate that
      // silently reused the same secret would let one node's trigger register over
      // the other's URL.
      for (const p of nodeTypesByType.get(original.data.nodeType)?.params ?? []) {
        if (p.autoGenerate) params[p.key] = genRandomToken()
      }
      const newNode: Node<FlowNodeData> = {
        ...original,
        id: nextNodeId(),
        position: { x: original.position.x + 36, y: original.position.y + 36 },
        selected: false,
        data: { ...original.data, params },
      }
      setNodes((prev) => [...prev, newNode])
      setSelectedNodeId(newNode.id)
      markDirty()
    },
    [recordHistory, markDirty, nodeTypesByType],
  )

  function handleChangeNodeMeta(key: 'title' | 'note', value: string) {
    if (!selectedNodeId) return
    recordHistory(false)
    setNodes((prev) =>
      prev.map((n) => (n.id === selectedNodeId ? { ...n, data: { ...n.data, [key]: value } } : n)),
    )
    markDirty()
  }

  // Highlights whichever node the running script just reached (see the
  // "__NODE_START__" marker RunPanel parses out of the log stream) — not a user edit,
  // so it deliberately skips recordHistory/markDirty. Only touches the two node
  // objects whose flag actually changes, so unrelated nodes keep a stable reference.
  function handleNodeExecuting(nodeId: string | null) {
    setNodes((prev) =>
      prev.map((n) => {
        const isExecuting = n.id === nodeId
        if (Boolean(n.data.isExecuting) === isExecuting) return n
        return { ...n, data: { ...n.data, isExecuting } }
      }),
    )
  }

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null
  const selectedSpec = selectedNode ? nodeTypesByType.get(selectedNode.data.nodeType) : undefined

  const upstreamVariables = useMemo(
    () => (selectedNode ? getUpstreamVariables(selectedNode.id, nodes, edges, nodeTypesByType) : []),
    [selectedNode, nodes, edges, nodeTypesByType],
  )

  const upstreamFieldMapOptions = useMemo(
    () => (selectedNode ? getUpstreamFieldMapOptions(selectedNode.id, nodes, edges) : []),
    [selectedNode, nodes, edges],
  )

  async function handlePreviewVariable(source: VariableSource) {
    const { value } = await workflowsApi.previewVariable(
      projectId!,
      workflowId!,
      toWFNodes(nodes),
      toWFEdges(edges),
      source.nodeId,
      source.variableName,
      startNodeId,
    )
    return value
  }

  const handleRunNodePreview = useCallback(
    async (nodeId: string) => {
      const node = nodesRef.current.find((n) => n.id === nodeId)
      if (!node) throw new Error('Node not found')
      const autoLoop = node.data.params.autoLoop
      const isAutoLoop = autoLoop === undefined ? true : Boolean(autoLoop)
      const variableName = isAutoLoop ? 'data' : String(node.data.params.resultVar ?? '').trim()
      if (!variableName) {
        throw new Error('Set "Result Variable" first (or turn "Loop automatically" back on).')
      }
      const { value } = await workflowsApi.previewVariable(
        projectId!,
        workflowId!,
        toWFNodes(nodesRef.current),
        toWFEdges(edgesRef.current),
        nodeId,
        variableName,
        startNodeId,
      )
      return value
    },
    [projectId, workflowId, startNodeId],
  )

  const handleSaveFieldMap = useCallback(
    (nodeId: string, fieldMap: string[]) => {
      setNodes((prev) => prev.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, fieldMap } } : n)))
      markDirty()
    },
    [markDirty],
  )

  function handleExport() {
    const payload = { name, nodes: toWFNodes(nodesRef.current), edges: toWFEdges(edgesRef.current), startNodeId }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${name.trim() || 'workflow'}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

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
        <input
          className="topbar-title-input"
          value={name}
          placeholder="Workflow name"
          onChange={(e) => {
            setName(e.target.value)
            markDirty()
          }}
          onBlur={() => {
            // The rest of the graph relies on the 2s debounce, but leaving this field
            // (clicking elsewhere, navigating away) shouldn't have to race it — save
            // immediately once the user is done editing the name specifically.
            if (dirty) saveMutation.mutate()
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') e.currentTarget.blur()
          }}
          size={Math.max(8, name.length)}
        />
        <div className="topbar-right">
          {saveMutation.isPending ? (
            <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Saving…</span>
          ) : (
            dirty && <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Unsaved changes</span>
          )}

          {publishError && (
            <span className="error-banner" style={{ padding: '2px 8px', fontSize: 12 }}>
              {publishError}
            </span>
          )}

          <div className="topbar-group">
            <button className="icon-btn" onClick={undo} disabled={!canUndo} title="Undo (Ctrl+Z)">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 14 4 9l5-5" />
                <path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" />
              </svg>
            </button>
            <button className="icon-btn" onClick={redo} disabled={!canRedo} title="Redo (Ctrl+Y)">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m15 14 5-5-5-5" />
                <path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13" />
              </svg>
            </button>
          </div>

          <button className="icon-btn" onClick={handleExport} title="Export workflow as JSON">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
          </button>

          <div className="topbar-divider" />

          <button
            className={`publish-toggle ${workflow?.published ? 'is-published' : ''}`}
            onClick={() => (workflow?.published ? unpublishMutation.mutate() : publishMutation.mutate())}
            disabled={workflow?.published ? unpublishMutation.isPending : publishMutation.isPending || dirty}
            title={
              workflow?.published
                ? 'Unpublish — stops the Schedule/Webhook trigger from firing'
                : dirty
                  ? 'Save your changes before publishing'
                  : "Publish — lets this workflow's Schedule/Webhook trigger fire"
            }
          >
            <span className="dot" />
            {workflow?.published ? 'Published' : 'Publish'}
          </button>

          <button className="btn btn-primary btn-sm" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending || !dirty}>
            Save
          </button>
        </div>
      </div>

      <div className="editor-body" style={{ gridTemplateRows: `1fr ${bottomPanelHeight}px` }}>
        <NodePalette onAddNode={(spec) => handleAddNode(spec)} />

        <FlowCanvas
          ref={flowCanvasRef}
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
          onDuplicateNode={handleDuplicateNode}
          onRunNodePreview={handleRunNodePreview}
          onSaveFieldMap={handleSaveFieldMap}
          nodeTypesByType={nodeTypesByType}
          startNodeId={startNodeId}
          onSetStartNode={handleSetStartNode}
        />

        <div className="side-panel">
          <NodeConfigPanel
            node={selectedNode}
            spec={selectedSpec}
            onChangeParam={handleChangeParam}
            onChangeMeta={handleChangeNodeMeta}
            onDeleteNode={handleDeleteNode}
            upstreamVariables={upstreamVariables}
            onPreviewVariable={handlePreviewVariable}
            upstreamFieldMapOptions={upstreamFieldMapOptions}
            projectId={projectId!}
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
            <button
              className={`panel-tab ${activeTab === 'executions' ? 'active' : ''}`}
              onClick={() => setActiveTab('executions')}
            >
              Executions
            </button>
          </div>
          <div className="panel-content">
            {activeTab === 'code' && projectId && workflowId && (
              <CodePreviewPanel
                projectId={projectId}
                workflowId={workflowId}
                nodes={nodes}
                edges={edges}
                startNodeId={startNodeId}
              />
            )}
            {activeTab === 'run' && projectId && workflowId && (
              <RunPanel
                projectId={projectId}
                workflowId={workflowId}
                nodes={nodes}
                edges={edges}
                startNodeId={startNodeId}
                onNodeExecuting={handleNodeExecuting}
              />
            )}
            {activeTab === 'executions' && projectId && workflowId && (
              <ExecutionsPanel projectId={projectId} workflowId={workflowId} />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
