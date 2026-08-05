import { useEffect, useRef, useState } from 'react'
import type { Edge, Node } from '@xyflow/react'
import { LuSearch } from 'react-icons/lu'
import { workflowsApi } from '../api/workflows'
import { runsApi } from '../api/runs'
import { toWFEdges, toWFNodes } from './convert'
import type { FlowEdgeData, FlowNodeData } from './types'
import { ApiError } from '../api/client'
import type { RunStatus } from '../types/workflow'

interface Props {
  projectId: string
  workflowId: string
  nodes: Node<FlowNodeData>[]
  edges: Edge<FlowEdgeData>[]
  onNodeExecuting: (nodeId: string | null) => void
}

interface LogEntry {
  text: string
  level: string
}

const STATUS_LABELS: Record<RunStatus, string> = {
  running: 'Running…',
  success: '✓ Finished successfully',
  error: '✗ Run failed',
  cancelled: '⏹ Stopped',
}

// Every node's generated code prints this (see engine.py) right before that node's own
// action runs — lets the canvas highlight whichever node is currently executing. Not
// one of the node's own descriptive logs, so it's filtered out of the visible log list.
const NODE_START_MARKER = '__NODE_START__'

// Unique prefix stamped onto anything the inspector copies, so this app's clipboard
// watcher (see startClipboardWatch below) can tell "the user pressed C on an element"
// apart from any other unrelated thing that might land on the clipboard.
const INSPECTOR_COPY_MARKER = '[[AM_INSPECTOR_COPY]]'

// One-line JS injected into the live paused page via page.evaluate() — adds a mouseover
// listener that outlines the hovered element and shows a floating tooltip with its
// tag/selector/id/class/size/attrs/text, right next to the cursor in the Chrome window
// itself (no round-trip through our own UI needed). This snippet travels JS -> our fetch
// call -> Python (pdb reads and exec's the line, re-parsing the triple-quoted string) ->
// back into JS via page.evaluate — Python's own string parsing sits in the middle of that
// chain, so any backslash escape (\n, \s, ...) gets silently unescaped by Python before it
// ever reaches the browser, corrupting the JS source. Easiest fix: use zero backslashes —
// build the tooltip as an array of lines (one <div> each) instead of "\n"-joined text, and
// split(' ') instead of a /\s+/ regex.
const INSPECTOR_JS =
  "(function(){if(window.__amInspector)return;window.__amInspector=true;" +
  "var NL=String.fromCharCode(10);" +
  // Copy-to-clipboard is deliberately NOT wired to click — Playwright's own .click()
  // calls dispatch real DOM click events too, so intercepting click here would also
  // hijack the rest of the automation once the user hits Continue. A keydown (not
  // firing while the page's own input/textarea/contenteditable has focus) is a
  // hover-scoped action that can't collide with anything the script itself does.
  "function copyText(t){if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).catch(function(){fallbackCopy(t);});}else{fallbackCopy(t);}}" +
  "function fallbackCopy(t){var ta=document.createElement('textarea');ta.value=t;ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove();}" +
  "function flash(msg){var f=document.createElement('div');f.textContent=msg;f.style.cssText='position:fixed;top:8px;right:8px;z-index:2147483647;background:#0a7d2c;color:#fff;font:12px sans-serif;padding:8px 12px;border-radius:6px;box-shadow:0 2px 10px rgba(0,0,0,.5)';document.documentElement.appendChild(f);setTimeout(function(){f.remove();},1200);}" +
  // Shows the actual copied text (not just a generic "Copied!") so it's easy to eyeball
  // which selector/xpath got grabbed without having to paste it somewhere first.
  "function flashCopy(lines){var f=document.createElement('div');f.style.cssText='position:fixed;top:8px;right:8px;z-index:2147483647;background:#0a7d2c;color:#fff;font:11px monospace;padding:8px 12px;border-radius:6px;box-shadow:0 2px 10px rgba(0,0,0,.5);max-width:360px;cursor:pointer;';var t=document.createElement('div');t.textContent='Copied to clipboard (click to dismiss):';t.style.cssText='font:12px sans-serif;font-weight:bold;margin-bottom:4px;';f.appendChild(t);lines.forEach(function(l){var d=document.createElement('div');d.textContent=l;f.appendChild(d);});f.addEventListener('click',function(){f.remove();});document.documentElement.appendChild(f);setTimeout(function(){f.remove();},15000);}" +
  "var box=document.createElement('div');" +
  "box.style.cssText='position:fixed;z-index:2147483647;pointer-events:none;background:#111;color:#0f0;font:11px monospace;padding:6px 8px;border-radius:4px;max-width:360px;box-shadow:0 2px 10px rgba(0,0,0,.5);display:none';" +
  "document.documentElement.appendChild(box);" +
  // Visible, unmissable confirmation the moment this attaches — without it, a silent
  // failure (wrong page, script error swallowed somewhere) looks identical to "just
  // hover and see nothing", which is exactly the ambiguity that's hard to debug.
  "flash('Element inspector active - hover an element, press C to copy its data');" +
  "var hi=null;" +
  "var curLines=[];" +
  "function sel(el){if(el.id)return '#'+el.id;if(el.className&&typeof el.className==='string'&&el.className.trim())return '.'+el.className.trim().split(' ').filter(Boolean).join('.');return el.tagName.toLowerCase();}" +
  "function idx(el){var i=1,s=el.previousElementSibling;while(s){if(s.tagName===el.tagName)i++;s=s.previousElementSibling;}return i;}" +
  "function fullXPath(el){var path='',cur=el;while(cur&&cur.nodeType===1){path='/'+cur.tagName.toLowerCase()+'['+idx(cur)+']'+path;cur=cur.parentElement;}return path;}" +
  "function smartXPath(el){if(el.id)return '//*[@id=\"'+el.id+'\"]';var segs=[],cur=el;while(cur&&cur.nodeType===1&&!cur.id){segs.unshift(cur.tagName.toLowerCase()+'['+idx(cur)+']');cur=cur.parentElement;}if(cur&&cur.id)return '//*[@id=\"'+cur.id+'\"]/'+segs.join('/');return fullXPath(el);}" +
  "document.addEventListener('mouseover',function(e){" +
  "var el=e.target;if(hi)hi.style.outline='';el.style.outline='2px solid #ff2d55';hi=el;" +
  "var r=el.getBoundingClientRect();" +
  "var txt=(el.innerText||el.value||'').trim().slice(0,80);" +
  "var attrs=Array.prototype.slice.call(el.attributes).map(function(a){return a.name+'='+a.value;}).slice(0,6).join(', ');" +
  "curLines=['<'+el.tagName.toLowerCase()+'>','CSS Selector: '+sel(el),'XPath: '+smartXPath(el),'Full XPath: '+fullXPath(el),'id: '+(el.id||'-'),'name: '+(el.getAttribute('name')||'-'),'class: '+(el.className||'-'),'size: '+Math.round(r.width)+'x'+Math.round(r.height),'attrs: '+(attrs||'-'),'text: '+(txt||'-')];" +
  "box.innerHTML='';" +
  "curLines.concat(['(press C to copy)']).forEach(function(l){var d=document.createElement('div');d.textContent=l;box.appendChild(d);});" +
  "box.style.left=Math.max(0,Math.min(e.clientX+16,window.innerWidth-380))+'px';" +
  "box.style.top=Math.max(0,Math.min(e.clientY+16,window.innerHeight-140))+'px';" +
  "box.style.display='block';" +
  "},true);" +
  "document.addEventListener('mouseout',function(){box.style.display='none';if(hi){hi.style.outline='';hi=null;}},true);" +
  "document.addEventListener('keydown',function(e){" +
  "if(!hi||curLines.length===0)return;" +
  "var active=document.activeElement;var tag=(active&&active.tagName||'').toLowerCase();" +
  "if(tag==='input'||tag==='textarea'||(active&&active.isContentEditable))return;" +
  "if(e.key!=='c'&&e.key!=='C')return;" +
  `copyText('${INSPECTOR_COPY_MARKER}'+NL+curLines.join(NL));` +
  "flashCopy(curLines);" +
  "},true);" +
  "})();"

// Quick-start snippets for the pdb command line, one per action-style node type — picking
// one fills the input with a generic call the user then edits in place (the placeholder,
// when there is one, is pre-selected so typing immediately replaces it).
const PDB_SNIPPETS: { label: string; template: string; placeholder?: string }[] = [
  { label: 'Navigate', template: 'page.goto("https://example.com")', placeholder: '"https://example.com"' },
  { label: 'Fill Input', template: 'page.locator("#selector").fill("value")', placeholder: '"#selector"' },
  {
    label: 'Select Option',
    template: 'page.locator("#selector").select_option("value")',
    placeholder: '"#selector"',
  },
  { label: 'Click', template: 'page.locator("#selector").click()', placeholder: '"#selector"' },
  { label: 'Hover', template: 'page.locator("#selector").hover()', placeholder: '"#selector"' },
  { label: 'Wait for element', template: 'page.locator("#selector").wait_for()', placeholder: '"#selector"' },
  { label: 'Get Text', template: 'p page.locator("#selector").inner_text()', placeholder: '"#selector"' },
  { label: 'Element Present?', template: 'p page.locator("#selector").count() > 0', placeholder: '"#selector"' },
]

// add_init_script re-runs this on every future navigation on this page (Playwright has no
// retroactive effect on the already-loaded page though), so it's paired with an immediate
// evaluate() to also cover the page as it stands right now.
const INSPECTOR_COMMAND = `page.add_init_script("""${INSPECTOR_JS}"""); page.evaluate("""${INSPECTOR_JS}""")`

export default function RunPanel({ projectId, workflowId, nodes, edges, onNodeExecuting }: Props) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [status, setStatus] = useState<RunStatus | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pdbCommand, setPdbCommand] = useState('')
  const [inspectorActive, setInspectorActive] = useState(false)
  const [copiedPreview, setCopiedPreview] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const runIdRef = useRef<string | null>(null)
  const pdbInputRef = useRef<HTMLInputElement>(null)
  const lastClipboardRef = useRef<string | null>(null)
  const clipboardPollRef = useRef<number | null>(null)

  // Bridges the copy triggered by the inspector's "press C" (which happens entirely
  // inside the separate Chrome window Playwright launched, with no channel back to
  // this app) into our own UI — the only thing both sides can see is the OS clipboard,
  // so this polls it and surfaces a change as a toast here. Reading the clipboard needs
  // this document to have focus; while the user is over on the Chrome window it'll fail
  // every tick (silently, on purpose) and simply pick up the change once they switch back.
  function startClipboardWatch() {
    stopClipboardWatch()
    navigator.clipboard
      .readText()
      .then((text) => {
        lastClipboardRef.current = text
      })
      .catch(() => {
        lastClipboardRef.current = null
      })
    clipboardPollRef.current = window.setInterval(() => {
      navigator.clipboard
        .readText()
        .then((text) => {
          if (!text || text === lastClipboardRef.current) return
          lastClipboardRef.current = text
          // Only surface clipboard changes that actually came from the inspector —
          // anything else on the clipboard (copied from elsewhere) is none of our business.
          if (text.startsWith(INSPECTOR_COPY_MARKER)) {
            setCopiedPreview(text.slice(INSPECTOR_COPY_MARKER.length).replace(/^\n+/, ''))
          }
        })
        .catch(() => {
          // Document not focused, or permission not granted yet — just skip this tick.
        })
    }, 700)
  }

  function stopClipboardWatch() {
    if (clipboardPollRef.current !== null) {
      window.clearInterval(clipboardPollRef.current)
      clipboardPollRef.current = null
    }
  }

  useEffect(() => stopClipboardWatch, [])

  useEffect(() => {
    if (!running) stopClipboardWatch()
  }, [running])

  function handleDismissCopiedPreview() {
    setCopiedPreview(null)
    // Clearing the clipboard right away would stomp on whatever the user pastes next —
    // give them a real window to paste it, and only clear it 30s later, and only if
    // it's still our own marker-prefixed content (never someone else's copy in between).
    window.setTimeout(() => {
      navigator.clipboard
        .readText()
        .then((current) => {
          if (!current.startsWith(INSPECTOR_COPY_MARKER)) return
          navigator.clipboard.writeText('').then(() => {
            lastClipboardRef.current = ''
          })
        })
        .catch(() => {
          // Best-effort — no focus/permission just means we leave the clipboard alone.
        })
    }, 30000)
  }

  async function handleRun() {
    setLogs([])
    setStatus(null)
    setError(null)
    setRunning(true)
    onNodeExecuting(null)
    runIdRef.current = null

    try {
      const { runId } = await workflowsApi.run(projectId, workflowId, toWFNodes(nodes), toWFEdges(edges))
      runIdRef.current = runId
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/runs/${runId}`)
      wsRef.current = ws

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)
        if (msg.type === 'log') {
          if (msg.text.startsWith(NODE_START_MARKER)) {
            onNodeExecuting(msg.text.slice(NODE_START_MARKER.length).trim())
            return
          }
          setLogs((prev) => [...prev, { text: msg.text, level: msg.level }])
        } else if (msg.type === 'done') {
          setStatus(msg.status)
          setRunning(false)
          onNodeExecuting(null)
          ws.close()
        } else if (msg.type === 'error') {
          setError(msg.detail)
          setRunning(false)
          onNodeExecuting(null)
          ws.close()
        }
      }
      ws.onerror = () => {
        setError('WebSocket connection error')
        setRunning(false)
        onNodeExecuting(null)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to start run')
      setRunning(false)
      onNodeExecuting(null)
    }
  }

  async function handleContinue() {
    if (!runIdRef.current) return
    try {
      await runsApi.continue_(runIdRef.current)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send continue')
    }
  }

  async function handleActivateInspector() {
    if (!runIdRef.current) return
    try {
      await runsApi.sendInput(runIdRef.current, INSPECTOR_COMMAND)
      setInspectorActive(true)
      startClipboardWatch()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to activate the inspector')
    }
  }

  async function handleSendPdbCommand() {
    if (!runIdRef.current || !pdbCommand.trim()) return
    try {
      await runsApi.sendInput(runIdRef.current, pdbCommand)
      setPdbCommand('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send command')
    }
  }

  function insertSnippet(snippet: { template: string; placeholder?: string }) {
    setPdbCommand(snippet.template)
    // rAF can be throttled when this tab isn't focused (e.g. the user alt-tabbed to
    // look at the paused browser window), so a plain macrotask is more reliable here
    // than syncing with a paint we may not get promptly.
    setTimeout(() => {
      const el = pdbInputRef.current
      if (!el) return
      el.focus()
      if (!snippet.placeholder) {
        el.setSelectionRange(snippet.template.length, snippet.template.length)
        return
      }
      const start = snippet.template.indexOf(snippet.placeholder)
      if (start !== -1) {
        el.setSelectionRange(start + 1, start + snippet.placeholder.length - 1)
      }
    }, 0)
  }

  async function handleStop() {
    if (!runIdRef.current) return
    try {
      await runsApi.stop(runIdRef.current)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to stop run')
    }
  }

  function handleLogAreaKeyDown(e: React.KeyboardEvent) {
    const isCtrlC = (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c'
    if (!isCtrlC || !running) return
    // If the user has text selected, let the browser copy it as usual — only treat
    // Ctrl+C as "stop" when there's nothing to copy, like a real terminal would.
    const hasSelection = (window.getSelection()?.toString().length ?? 0) > 0
    if (hasSelection) return
    e.preventDefault()
    handleStop()
  }

  return (
    <div tabIndex={0} onKeyDown={handleLogAreaKeyDown} style={{ outline: 'none' }}>
      <button className="btn btn-primary btn-sm" onClick={handleRun} disabled={running || nodes.length === 0}>
        {running ? 'Running…' : '▶ Run'}
      </button>
      {running && (
        <button className="btn btn-sm" onClick={handleStop} style={{ marginLeft: 8 }} title="Stop (Ctrl+C)">
          ⏹ Stop
        </button>
      )}
      {running && (
        <button className="btn btn-sm" onClick={handleContinue} style={{ marginLeft: 8 }}>
          ⏵ Continue past breakpoint
        </button>
      )}
      {running && (
        <button
          className="btn btn-sm"
          onClick={handleActivateInspector}
          style={{ marginLeft: 8, display: 'inline-flex', alignItems: 'center', gap: 4 }}
          title="Inspect elements — hover any element in the Chrome window to see its details"
        >
          <LuSearch size={13} />
          Inspector
        </button>
      )}

      {running && (
        <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 6 }}>
          Click into this panel and press Ctrl+C to stop execution (when nothing is selected). Every node runs
          inside a try/except — if the log stops advancing, it's likely paused (either an explicit breakpoint,
          or an error in the last node); click "Continue", or type a pdb command below (n, s, p &lt;expr&gt;, l, c,
          ...).
        </div>
      )}

      {running && (
        <div style={{ marginTop: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 4 }}>
            <select
              value=""
              onChange={(e) => {
                const snippet = PDB_SNIPPETS.find((s) => s.label === e.target.value)
                if (snippet) insertSnippet(snippet)
                e.target.value = ''
              }}
              title="Insert a starting point for a common action, then edit the selector/value in place"
              style={{
                fontSize: 11,
                padding: '2px 4px',
                border: '1px solid var(--border)',
                borderRadius: 4,
                background: 'var(--bg)',
                color: 'var(--text-muted)',
              }}
            >
              <option value="">Insert command…</option>
              {PDB_SNIPPETS.map((s) => (
                <option key={s.label} value={s.label}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              ref={pdbInputRef}
              value={pdbCommand}
              onChange={(e) => setPdbCommand(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSendPdbCommand()
              }}
              placeholder="pdb command, e.g. p item"
              style={{
                flex: 1,
                fontFamily: 'var(--mono)',
                fontSize: 13,
                padding: '6px 8px',
                border: '1px solid var(--border)',
                borderRadius: 6,
                background: 'var(--bg)',
                color: 'var(--text)',
              }}
            />
            <button className="btn btn-sm" onClick={handleSendPdbCommand}>
              Send
            </button>
          </div>
        </div>
      )}

      {status && <div className={`run-status ${status}`}>{STATUS_LABELS[status]}</div>}
      {error && <div className="error-banner">{error}</div>}

      <div style={{ marginTop: 8 }}>
        {logs.map((log, i) => (
          <div key={i} className={`log-line ${log.level === 'error' ? 'error' : ''}`}>
            {log.text}
          </div>
        ))}
      </div>

      {inspectorActive && (
        <div className="modal-overlay" onClick={() => setInspectorActive(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <LuSearch size={18} />
              Modo inspecionador ativado
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13, margin: 0 }}>
              Passe o mouse sobre qualquer elemento na janela do Chrome para ver seus detalhes (CSS Selector,
              XPath, Full XPath, id, name, class, tamanho, atributos, texto). Pressione <strong>C</strong>{' '}
              enquanto o mouse estiver em cima do elemento para copiar esses dados — assim que esta aba estiver
              em foco, um modal aparece aqui com o que foi copiado e fica aberto até você clicar em "Dispensar"
              (dá pra pressionar C em vários elementos seguidos para comparar). Continua ativo mesmo se a
              página navegar.
            </p>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={() => setInspectorActive(false)}>
                Ok
              </button>
            </div>
          </div>
        </div>
      )}

      {copiedPreview && (
        <div className="modal-overlay" onClick={handleDismissCopiedPreview}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ width: 460 }}>
            <h3>Copiado — escolha o campo</h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 12, margin: '0 0 10px' }}>
              Pressione <strong>C</strong> sobre outro elemento na janela do Chrome para atualizar — este modal
              fica aberto até você dispensar.
            </p>
            <pre
              style={{
                margin: 0,
                fontFamily: 'var(--mono)',
                fontSize: 12,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: '8px 10px',
                maxHeight: 260,
                overflow: 'auto',
              }}
            >
              {copiedPreview}
            </pre>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleDismissCopiedPreview}>
                Dispensar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
