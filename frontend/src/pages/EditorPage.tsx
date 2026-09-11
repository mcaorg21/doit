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
import { launchApi, type CliProvider } from '../api/launch'
import { ApiError } from '../api/client'
import { nodeTypesApi } from '../api/nodeTypes'
import FlowCanvas, { type FlowCanvasHandle } from '../editor/FlowCanvas'
import NodePalette from '../editor/NodePalette'
import NodeConfigPanel from '../editor/NodeConfigPanel'
import CodePreviewPanel from '../editor/CodePreviewPanel'
import RunPanel from '../editor/RunPanel'
import ExecutionsPanel from '../editor/ExecutionsPanel'
import { toWFEdges, toWFNodes, wfEdgeToFlowEdge, wfNodeToFlowNode } from '../editor/convert'
import { getUpstreamVariables, getUpstreamFieldMapOptions, type VariableSource } from '../editor/graph'
import { arrangeWorkflowNodes } from '../editor/layout'
import { genRandomToken } from '../editor/randomToken'
import type { FlowEdgeData, FlowNodeData } from '../editor/types'
import type { NodeTypeSpec } from '../types/nodeType'
import type { WFEdge as WFEdgeModel, WFNode as WFNodeModel } from '../types/workflow'

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
  const [pendingDeleteNodeIds, setPendingDeleteNodeIds] = useState<string[]>([])
  const [notesOpen, setNotesOpen] = useState(false)
  const [notesDraft, setNotesDraft] = useState('')
  const [notesError, setNotesError] = useState<string | null>(null)

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
  // The node a Shift+click range is measured from — set on any plain/Ctrl click,
  // left alone on a Shift+click so repeated Shift+clicks keep extending from the
  // same starting point (matches how Explorer/Sheets range-select behaves).
  const selectionAnchorRef = useRef<string | null>(null)

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

  // Notes: a per-workflow markdown doc (stored as a real sibling .md file, not part
  // of the workflow's own JSON — see backend/app/storage/workflow_store.py) meant to
  // guide a human AND an AI working on this workflow via the MCP connector (its
  // get_workflow tool returns this same text). Fetched lazily only once the modal is
  // actually opened, not on every editor page load.
  const notesQuery = useQuery({
    queryKey: ['workflowNotes', projectId, workflowId],
    queryFn: () => workflowsApi.getNotes(projectId!, workflowId!),
    enabled: notesOpen && !!projectId && !!workflowId,
  })

  useEffect(() => {
    if (notesQuery.data) setNotesDraft(notesQuery.data.notes)
  }, [notesQuery.data])

  const saveNotesMutation = useMutation({
    mutationFn: (notes: string) => workflowsApi.setNotes(projectId!, workflowId!, notes),
    onSuccess: (result) => {
      setNotesError(null)
      queryClient.setQueryData(['workflowNotes', projectId, workflowId], result)
      setNotesOpen(false)
    },
    onError: (err: unknown) => {
      setNotesError(err instanceof ApiError || err instanceof Error ? err.message : 'Failed to save notes')
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
        const selectedIds = nodesRef.current.filter((n) => n.selected).map((n) => n.id)
        if (selectedIds.length === 0) return
        e.preventDefault()
        requestDeleteNode(selectedIds)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
    // requestDeleteNode isn't declared yet at this point in the component body (it's
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

  // Handles both a single delete (icon/config-panel/one node selected) and a bulk
  // delete (multi-select via Ctrl/Shift + Delete) as ONE undo step either way — a
  // loop calling a single-node deleter here would push one history snapshot per
  // node, all from the same pre-delete state (recordHistory snapshots nodesRef/
  // edgesRef, which only update via the effect after render, so they wouldn't have
  // advanced between synchronous loop iterations), cluttering undo with duplicates.
  const handleDeleteNodesByIds = useCallback(
    (nodeIds: string[]) => {
      if (nodeIds.length === 0) return
      const idSet = new Set(nodeIds)
      recordHistory(true)
      setNodes((prev) => prev.filter((n) => !idSet.has(n.id)))
      setEdges((prev) => prev.filter((e) => !idSet.has(e.source) && !idSet.has(e.target)))
      setSelectedNodeId((current) => (current && idSet.has(current) ? null : current))
      // A deleted Start Node would otherwise leave a dangling reference — harmless to
      // codegen (it just falls back to erroring on ambiguity again like before this
      // node existed), but clearing it here keeps the picked start node always valid.
      setStartNodeId((current) => (current && idSet.has(current) ? null : current))
      markDirty()
    },
    [recordHistory, markDirty],
  )

  // Ctrl/Cmd+click toggling one node in/out of the selection is React Flow's own
  // default behavior (already applied to `nodes[].selected` before this fires) — left
  // alone here. Shift+click is custom: React Flow has no built-in "range select"
  // between two clicked nodes, so this adds one — ordered by x position (graphs in
  // this app read left-to-right, including everything MCP-built workflows already
  // lay out that way) rather than anything graph-topology-based, since that's simple
  // and predictable for the free-form canvas.
  const handleSelectNode = useCallback((nodeId: string | null, event?: React.MouseEvent) => {
    setSelectedNodeId(nodeId)
    if (nodeId === null) {
      selectionAnchorRef.current = null
      return
    }
    if (event?.shiftKey && selectionAnchorRef.current) {
      const anchorId = selectionAnchorRef.current
      const orderedByX = [...nodesRef.current].sort((a, b) => a.position.x - b.position.x)
      const anchorIndex = orderedByX.findIndex((n) => n.id === anchorId)
      const targetIndex = orderedByX.findIndex((n) => n.id === nodeId)
      if (anchorIndex !== -1 && targetIndex !== -1) {
        const [start, end] = anchorIndex < targetIndex ? [anchorIndex, targetIndex] : [targetIndex, anchorIndex]
        const rangeIds = new Set(orderedByX.slice(start, end + 1).map((n) => n.id))
        setNodes((prev) => prev.map((n) => (rangeIds.has(n.id) ? { ...n, selected: true } : n)))
      }
      // Anchor stays put so a further Shift+click keeps extending the same range.
      return
    }
    // Plain click or Ctrl+click: this node becomes the new anchor for a future
    // Shift+click range.
    selectionAnchorRef.current = nodeId
  }, [])

  const handleSetStartNode = useCallback(
    (nodeId: string) => {
      setStartNodeId((current) => (current === nodeId ? null : nodeId))
      markDirty()
    },
    [markDirty],
  )

  function requestDeleteNode(nodeIds: string[]) {
    if (nodeIds.length === 0) return
    setPendingDeleteNodeIds(nodeIds)
  }

  function handleDeleteNode() {
    if (!selectedNodeId) return
    requestDeleteNode([selectedNodeId])
  }

  function confirmDeleteNode() {
    if (pendingDeleteNodeIds.length === 0) return
    handleDeleteNodesByIds(pendingDeleteNodeIds)
    setPendingDeleteNodeIds([])
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

  function handleNodeFailed(nodeId: string | null) {
    setNodes((prev) =>
      prev.map((n) => {
        if (nodeId === null) {
          return n.data.hasExecutionError ? { ...n, data: { ...n.data, hasExecutionError: false } } : n
        }
        const isFailedNode = n.id === nodeId
        if (!isFailedNode && !n.data.isExecuting) return n
        return {
          ...n,
          data: {
            ...n.data,
            isExecuting: false,
            hasExecutionError: isFailedNode ? true : n.data.hasExecutionError,
          },
        }
      }),
    )
    if (nodeId !== null) {
      queryClient.invalidateQueries({ queryKey: ['workflow', projectId, workflowId] })
      queryClient.invalidateQueries({ queryKey: ['workflows', projectId] })
    }
  }

  // Mirrors handleNodeExecuting — highlights whichever node the running script is
  // currently sitting at a breakpoint on (see the "__NODE_PAUSED__" marker RunPanel
  // parses out of the log stream). Also not a user edit.
  function handleNodePaused(nodeId: string | null) {
    setNodes((prev) =>
      prev.map((n) => {
        const isPaused = n.id === nodeId
        if (Boolean(n.data.isPaused) === isPaused) return n
        return { ...n, data: { ...n.data, isPaused } }
      }),
    )
  }

  // Applies a node/edge mutation that the MCP server (see backend/app/mcp/server.py)
  // already persisted, received live over /ws/workflows/{id} — these deliberately do
  // NOT call markDirty()/recordHistory(): the change is already saved on the server,
  // so re-arming autosave here would at best redundantly PUT back content that
  // already matches it, and at worst race a still-in-flight remote edit if the
  // debounced save fires from a snapshot that missed a very recent event. Ctrl+Z
  // doesn't cover these edits for the same reason (no local history entry).
  const applyRemoteNodeAdded = useCallback(
    (wfNode: WFNodeModel) => {
      setNodes((prev) => (prev.some((n) => n.id === wfNode.id) ? prev : [...prev, wfNodeToFlowNode(wfNode, nodeTypesByType)]))
    },
    [nodeTypesByType],
  )

  const applyRemoteNodeUpdated = useCallback(
    (wfNode: WFNodeModel) => {
      setNodes((prev) => prev.map((n) => (n.id === wfNode.id ? wfNodeToFlowNode(wfNode, nodeTypesByType) : n)))
    },
    [nodeTypesByType],
  )

  const applyRemoteNodeRemoved = useCallback((nodeId: string) => {
    setNodes((prev) => prev.filter((n) => n.id !== nodeId))
    setEdges((prev) => prev.filter((e) => e.source !== nodeId && e.target !== nodeId))
  }, [])

  const applyRemoteEdgeAdded = useCallback((wfEdge: WFEdgeModel) => {
    setEdges((prev) => (prev.some((e) => e.id === wfEdge.id) ? prev : [...prev, wfEdgeToFlowEdge(wfEdge)]))
  }, [])

  const applyRemoteEdgeRemoved = useCallback((edgeId: string) => {
    setEdges((prev) => prev.filter((e) => e.id !== edgeId))
  }, [])

  // Live-build sync: while an MCP client (Claude Desktop/Code) drives
  // start_live_session/add_node/demo_node/etc. against this workflow, this reflects
  // each mutation on the canvas as it happens instead of requiring a manual refresh.
  useEffect(() => {
    if (!workflowId || !loaded) return
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/workflows/${workflowId}`)
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      switch (msg.type) {
        case 'node_added':
          applyRemoteNodeAdded(msg.node)
          break
        case 'node_updated':
          applyRemoteNodeUpdated(msg.node)
          break
        case 'node_removed':
          applyRemoteNodeRemoved(msg.nodeId)
          break
        case 'edge_added':
          applyRemoteEdgeAdded(msg.edge)
          break
        case 'edge_removed':
          applyRemoteEdgeRemoved(msg.edgeId)
          break
      }
    }
    return () => ws.close()
  }, [workflowId, loaded, applyRemoteNodeAdded, applyRemoteNodeUpdated, applyRemoteNodeRemoved, applyRemoteEdgeAdded, applyRemoteEdgeRemoved])

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

  const [launchResult, setLaunchResult] = useState<{ title: string; detail: string; ok: boolean } | null>(null)
  const [launchMenuOpen, setLaunchMenuOpen] = useState(false)
  const launchMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!launchMenuOpen) return
    function onClickOutside(e: MouseEvent) {
      if (launchMenuRef.current && !launchMenuRef.current.contains(e.target as globalThis.Node)) {
        setLaunchMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [launchMenuOpen])

  async function handleLaunchTerminal(provider: CliProvider) {
    setLaunchMenuOpen(false)
    const title = provider === 'codex' ? 'Terminal (Codex)' : 'Terminal (Claude Code)'
    try {
      const result = await launchApi.terminal(provider, projectId, workflowId)
      if (result.notify) {
        setLaunchResult({
          title,
          detail: result.detail ?? (result.launched ? 'Terminal aberto.' : 'Falha ao abrir terminal.'),
          ok: result.launched,
        })
      }
    } catch (err) {
      setLaunchResult({
        title,
        detail: err instanceof ApiError || err instanceof Error ? err.message : 'Failed to open terminal',
        ok: false,
      })
    }
  }

  async function handleLaunchClaudeDesktop() {
    setLaunchMenuOpen(false)
    try {
      const result = await launchApi.claudeDesktop()
      if (result.notify) {
        setLaunchResult({
          title: 'Claude Desktop',
          detail: result.detail ?? (result.launched ? 'Claude Desktop aberto.' : 'Falha ao abrir Claude Desktop.'),
          ok: result.launched,
        })
      }
    } catch (err) {
      setLaunchResult({
        title: 'Claude Desktop',
        detail: err instanceof ApiError || err instanceof Error ? err.message : 'Failed to open Claude Desktop',
        ok: false,
      })
    }
  }

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

  const handleArrangeNodes = useCallback(() => {
    if (nodesRef.current.length === 0) return
    recordHistory(true)
    setNodes(arrangeWorkflowNodes(nodesRef.current, edgesRef.current, startNodeId))
    markDirty()
    requestAnimationFrame(() => flowCanvasRef.current?.fitView())
  }, [recordHistory, markDirty, startNodeId])

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

          <button
            className="icon-btn"
            onClick={() => {
              setNotesError(null)
              setNotesOpen(true)
            }}
            title="Notes — a markdown guide for this workflow, also read by Claude/Codex via the MCP connector"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
              <line x1="9" y1="7" x2="15" y2="7" />
              <line x1="9" y1="11" x2="15" y2="11" />
            </svg>
          </button>

          <div className="launch-menu-wrap" ref={launchMenuRef}>
            <button
              className="icon-btn"
              onClick={() => setLaunchMenuOpen((v) => !v)}
              title="Continuar este workflow no Claude ou no Codex"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="url(#aiSparkleGradient)">
                <defs>
                  <linearGradient id="aiSparkleGradient" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
                    <stop offset="0" stopColor="#8B5CF6" />
                    <stop offset="1" stopColor="#EC4899" />
                  </linearGradient>
                </defs>
                <path d="M12 2 L14.5 9.5 L22 12 L14.5 14.5 L12 22 L9.5 14.5 L2 12 L9.5 9.5 Z" />
              </svg>
            </button>
            {launchMenuOpen && (
              <div className="launch-menu">
                <div className="launch-menu-label">Claude</div>
                <button className="launch-menu-item" onClick={() => handleLaunchTerminal('claude')}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="#D97757">
                    <rect x="10.6" y="2" width="2.8" height="20" rx="1.4" />
                    <rect x="10.6" y="2" width="2.8" height="20" rx="1.4" transform="rotate(45 12 12)" />
                    <rect x="10.6" y="2" width="2.8" height="20" rx="1.4" transform="rotate(90 12 12)" />
                    <rect x="10.6" y="2" width="2.8" height="20" rx="1.4" transform="rotate(135 12 12)" />
                  </svg>
                  Abrir no Terminal
                </button>
                <button className="launch-menu-item" onClick={handleLaunchClaudeDesktop}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="#D97757">
                    <rect x="10.6" y="2" width="2.8" height="20" rx="1.4" />
                    <rect x="10.6" y="2" width="2.8" height="20" rx="1.4" transform="rotate(45 12 12)" />
                    <rect x="10.6" y="2" width="2.8" height="20" rx="1.4" transform="rotate(90 12 12)" />
                    <rect x="10.6" y="2" width="2.8" height="20" rx="1.4" transform="rotate(135 12 12)" />
                  </svg>
                  Abrir no Claude Desktop
                </button>
                <div className="launch-menu-divider" />
                <div className="launch-menu-label">Codex</div>
                <button className="launch-menu-item" onClick={() => handleLaunchTerminal('codex')}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10A37F" strokeWidth="1.6">
                    <circle cx="18" cy="12" r="3.4" />
                    <circle cx="15" cy="17.2" r="3.4" />
                    <circle cx="9" cy="17.2" r="3.4" />
                    <circle cx="6" cy="12" r="3.4" />
                    <circle cx="9" cy="6.8" r="3.4" />
                    <circle cx="15" cy="6.8" r="3.4" />
                  </svg>
                  Abrir no Terminal
                </button>
              </div>
            )}
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
            className={`publish-toggle ${workflow?.published ? 'is-published' : ''} ${workflow?.hasError ? 'has-error' : ''}`}
            onClick={() => (workflow?.published ? unpublishMutation.mutate() : publishMutation.mutate())}
            disabled={workflow?.published ? unpublishMutation.isPending : publishMutation.isPending || dirty}
            title={
              workflow?.published
                ? 'Unpublish — stops the Schedule/Webhook trigger from firing'
                : workflow?.hasError
                  ? 'An unattended run of this workflow failed, so it was automatically unpublished — fix it, then click to publish again'
                  : dirty
                    ? 'Save your changes before publishing'
                    : "Publish — lets this workflow's Schedule/Webhook trigger fire"
            }
          >
            <span className="dot" />
            {workflow?.hasError ? 'Error' : workflow?.published ? 'Published' : 'Publish'}
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
          onSelectNode={handleSelectNode}
          onAddNode={handleAddNode}
          onToggleBreakpoint={handleToggleBreakpoint}
          onDeleteEdge={handleDeleteEdge}
          onDeleteNode={(nodeId) => requestDeleteNode([nodeId])}
          onDuplicateNode={handleDuplicateNode}
          onRunNodePreview={handleRunNodePreview}
          onSaveFieldMap={handleSaveFieldMap}
          nodeTypesByType={nodeTypesByType}
          startNodeId={startNodeId}
          onSetStartNode={handleSetStartNode}
          onArrangeNodes={handleArrangeNodes}
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
                onNodeFailed={handleNodeFailed}
                onNodePaused={handleNodePaused}
              />
            )}
            {activeTab === 'executions' && projectId && workflowId && (
              <ExecutionsPanel projectId={projectId} workflowId={workflowId} />
            )}
          </div>
        </div>
      </div>

      {pendingDeleteNodeIds.length > 0 && (
        <div className="modal-overlay" onClick={() => setPendingDeleteNodeIds([])}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>{pendingDeleteNodeIds.length === 1 ? 'Delete node' : `Delete ${pendingDeleteNodeIds.length} nodes`}</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>
              {pendingDeleteNodeIds.length === 1 ? (
                <>
                  Delete "
                  {nodes.find((n) => n.id === pendingDeleteNodeIds[0])?.data.title?.trim() ||
                    nodes.find((n) => n.id === pendingDeleteNodeIds[0])?.data.label ||
                    'this node'}
                  "? Its connections to other nodes will be removed too.
                </>
              ) : (
                <>
                  Delete these {pendingDeleteNodeIds.length} nodes ({pendingDeleteNodeIds
                    .map((id) => nodes.find((n) => n.id === id)?.data.title?.trim() || nodes.find((n) => n.id === id)?.data.label || id)
                    .join(', ')}
                  )? Their connections to other nodes will be removed too.
                </>
              )}
            </p>
            <div className="modal-actions">
              <button className="btn" onClick={() => setPendingDeleteNodeIds([])}>
                Cancel
              </button>
              <button className="btn btn-danger" onClick={confirmDeleteNode}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {notesOpen && (
        <div className="modal-overlay" onClick={() => setNotesOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 640 }}>
            <h3>Notes</h3>
            <p className="hint" style={{ marginBottom: 8 }}>
              A markdown guide for this workflow — what it does, known quirks, how to validate it. Saved as a plain
              .md file next to the workflow itself; Claude/Codex read it automatically via the MCP connector's
              get_workflow tool before working on this workflow.
            </p>
            {notesQuery.isLoading ? (
              <p className="hint">Loading…</p>
            ) : (
              <textarea
                autoFocus
                value={notesDraft}
                onChange={(e) => setNotesDraft(e.target.value)}
                placeholder={'# What this workflow does\n\n...'}
                style={{
                  width: '100%',
                  minHeight: 320,
                  fontFamily: 'var(--mono)',
                  fontSize: 13,
                  resize: 'vertical',
                  boxSizing: 'border-box',
                }}
              />
            )}
            {notesError && <div className="error-banner">{notesError}</div>}
            <div className="modal-actions">
              <button className="btn" onClick={() => setNotesOpen(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                disabled={saveNotesMutation.isPending || notesQuery.isLoading}
                onClick={() => saveNotesMutation.mutate(notesDraft)}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {launchResult && (
        <div className="modal-overlay" onClick={() => setLaunchResult(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>{launchResult.title}</h3>
            <p style={{ color: launchResult.ok ? 'var(--text-muted)' : 'var(--danger)', fontSize: 13, whiteSpace: 'pre-wrap' }}>
              {launchResult.detail}
            </p>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={() => setLaunchResult(null)}>
                OK
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
