# Auto-mation

Editor visual de workflows (estilo n8n) para automação de navegador com Playwright. Cada node adicionado ao canvas gera incrementalmente um script Python; o botão **Run** executa esse script real contra o Chrome via Playwright, com log ao vivo via WebSocket.

## Estrutura

- `backend/` — FastAPI + Playwright (Python). Projetos/workflows/runs são salvos como arquivos JSON em `data/`.
- `frontend/` — React + React Flow (`@xyflow/react`) + Vite.

## Rodando localmente

**Backend**

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chrome
python -m uvicorn app.main:app --port 8000
```

> **Não use `--reload` no Windows.** O modo `--reload` do uvicorn força o event loop `Selector` no Windows (necessário para o mecanismo de hot-reload), mas esse loop não suporta `asyncio.create_subprocess_exec` — que é como cada execução de workflow roda o script Python gerado. Sem `--reload`, o uvicorn usa `ProactorEventLoop` no Windows, que suporta subprocessos normalmente. Se você mudar código do backend, reinicie o processo manualmente.

**Frontend**

```powershell
cd frontend
npm install
npm run dev
```

Abre em `http://localhost:5173`. O Vite faz proxy de `/api` e `/ws` para `http://localhost:8000`.

## Troubleshooting

- **"address already in use" na porta 8000**: se você já rodou o backend com `--reload` antes (mesmo que tenha matado o processo), o Windows às vezes deixa a porta "presa" a um PID fantasma que não aparece mais em `Get-Process`. Reinicie o terminal (ou a máquina) para liberar a porta, ou rode o backend em outra porta (`--port 8001`) e ajuste os dois destinos de proxy em `frontend/vite.config.ts` para bater.
- **`ModuleNotFoundError: No module named 'playwright'` ao rodar um workflow**: o backend usa `sys.executable` (o Python do venv que está rodando o próprio uvicorn) para executar os scripts gerados por padrão — garanta que você iniciou o uvicorn de dentro do venv (`.venv\Scripts\python.exe -m uvicorn ...` ou com o venv ativado). Para apontar para outro interpretador, defina a variável de ambiente `AUTOMATION_PYTHON`.

## Tipos de node do MVP

`http_request` (fonte de dados — abre um laço `for item in data:`), `open_browser`, `goto` (Navigate), `fill` (Fill Input), `select_option`, `click`, `hover`. Valores de parâmetro podem referenciar o item atual do laço com `{{item.campo}}`.

Novos tipos de node são adicionados criando um arquivo em `backend/app/nodes/` (schema de parâmetros + função de geração de código) e uma linha de import em `backend/app/nodes/__init__.py` — o frontend renderiza a paleta e o formulário de configuração automaticamente a partir do schema, sem precisar de código novo no frontend para tipos de campo já suportados (`text`, `textarea`, `number`, `select`, `boolean`).

## Limitações do v1

Sem branching/condicionais (assume-se uma cadeia linear de nodes), sem laços aninhados/paralelos, `{{item.*}}` é a única forma de template suportada (não há referência a saída de nodes anteriores por id), sem autenticação multiusuário, sem deploy em nuvem.
