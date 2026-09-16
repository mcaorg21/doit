import { PDB_SNIPPETS } from './useWorkflowRun'
import type { WorkflowRun } from './useWorkflowRun'

interface Props {
  run: WorkflowRun
}

// The bottom "Logs" tab — the log stream, plus the pdb command line for interacting
// with a paused run (moved here from the floating canvas overlay so that overlay
// stays limited to Run/Stop/status/Continue/Inspector/Clipboard). Everything about
// actually STARTING a run lives in RunFloatingControls, which floats over the canvas
// instead and stays mounted regardless of which bottom-panel tab is open.
export default function LogsPanel({ run }: Props) {
  const { logs, running, pdbCommand, setPdbCommand, pdbInputRef, handleSendPdbCommand, insertSnippet, handleLogAreaKeyDown } = run

  return (
    <div tabIndex={0} onKeyDown={handleLogAreaKeyDown} style={{ outline: 'none' }}>
      {logs.length === 0 ? (
        <div className="node-config-empty">No logs yet — run the workflow to see its output here.</div>
      ) : (
        <div>
          {logs.map((log, i) => (
            <div key={i} className={`log-line ${log.level === 'error' ? 'error' : ''}`}>
              {log.text}
            </div>
          ))}
        </div>
      )}

      {running && (
        <div style={{ marginTop: 10, borderTop: '1px solid var(--border)', paddingTop: 8 }}>
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 6 }}>
            Click here and press Ctrl+C to stop execution (when nothing is selected). Every node runs inside a
            try/except — if the log stops advancing, it's likely paused (either an explicit breakpoint, or an
            error in the last node); click "Continue", or type a pdb command below (n, s, p &lt;expr&gt;, l, c,
            ...).
          </div>
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
    </div>
  )
}
