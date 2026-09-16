import { LuClipboard, LuSearch } from 'react-icons/lu'
import type { WorkflowRun } from './useWorkflowRun'
import { RUN_STATUS_LABELS } from './useWorkflowRun'

interface Props {
  run: WorkflowRun
}

// The n8n-style "big button floating over the canvas" control cluster — replaces the
// old button row that used to live inside the "Run" tab. Idle state is a single
// centered pill; once running, Stop appears beside it and the secondary controls
// (Continue/Inspector/Clipboard) fade in small underneath. The pdb command line (and
// its Ctrl+C-to-stop hint) lives in the Logs tab instead (see LogsPanel) — this
// overlay stays limited to starting/stopping a run and its quick side-actions.
export default function RunFloatingControls({ run }: Props) {
  const {
    running,
    status,
    error,
    canRun,
    handleRun,
    handleStop,
    handleContinue,
    handleActivateInspector,
    inspectorActive,
    setInspectorActive,
    clipboardOpen,
    clipboardText,
    clipboardHasNew,
    toggleClipboardBar,
  } = run

  return (
    <div className="run-float">
      {status && <div className={`run-float-status ${status}`}>{RUN_STATUS_LABELS[status]}</div>}
      {error && <div className="error-banner" style={{ marginBottom: 6 }}>{error}</div>}

      <div className="run-float-main">
        <button
          className="run-float-pill"
          onClick={handleRun}
          disabled={running || !canRun}
          title={canRun ? undefined : 'Add at least one node first'}
        >
          {running ? RUN_STATUS_LABELS.running : '▶ Run workflow'}
        </button>
        {running && (
          <button className="run-float-stop" onClick={handleStop} title="Stop (Ctrl+C)">
            ⏹ Stop
          </button>
        )}
      </div>

      {running && (
        <div className="run-float-secondary">
          <button className="btn btn-sm" onClick={handleContinue}>
            ⏵ Continue past breakpoint
          </button>
          <button
            className="btn btn-sm"
            onClick={handleActivateInspector}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
            title="Inspect elements — hover any element in the Chrome window to see its details"
          >
            <LuSearch size={13} />
            Inspector
          </button>
          <button
            className="btn btn-sm"
            onClick={toggleClipboardBar}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 4, position: 'relative' }}
            title="View the current clipboard content"
          >
            <LuClipboard size={13} />
            Clipboard
            {clipboardHasNew && !clipboardOpen && <span className="run-float-clipboard-dot" />}
          </button>
        </div>
      )}

      {clipboardOpen && (
        <div className="run-float-clipboard-box">
          <div className="run-float-clipboard-box-header">
            <span>Clipboard</span>
            <button className="icon-btn" title="Close" onClick={() => toggleClipboardBar()}>
              ✕
            </button>
          </div>
          <pre className="run-float-clipboard-box-content">
            {clipboardText || '(empty, or this tab doesn’t have permission/focus to read it yet)'}
          </pre>
        </div>
      )}

      {inspectorActive && (
        <div className="modal-overlay" onClick={() => setInspectorActive(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <LuSearch size={18} />
              Modo inspecionador ativado
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: 13, margin: 0 }}>
              Passe o mouse sobre qualquer elemento na janela do Chrome para ver seus detalhes (CSS Selector,
              XPath, Full XPath, id, name, class, tamanho, atributos, texto). <strong>Clique</strong> no elemento
              para congelar a caixinha no lugar — ela vira selecionável, então dá pra arrastar o mouse e copiar
              (Ctrl+C) só a linha que você quer, em vez do bloco inteiro. Clique no "x" ou aperte{' '}
              <strong>Esc</strong> pra descongelar e voltar a passar o mouse livremente. Prefere copiar tudo de
              uma vez? Pressione <strong>C</strong> (funciona tanto passando o mouse quanto com a caixinha
              congelada) e depois clique em "Clipboard" aqui em cima para ver o que foi copiado. Continua ativo
              mesmo se a página navegar.
            </p>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={() => setInspectorActive(false)}>
                Ok
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
