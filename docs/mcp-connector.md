# Conector MCP — construir automações via Claude ou Codex

Este app expõe um servidor MCP em `http://127.0.0.1:8001/mcp` (mesmo processo do backend, sobe junto com `npm run server:dev` / `npm run dev`). Ele permite pedir uma automação em linguagem natural direto no Claude (Desktop ou Code) ou no Codex CLI, e o próprio agente constrói o fluxo aqui dentro — usando só os nodes que este app já suporta, nunca inventando um tipo de node novo. Para sequências simples (navegar, preencher, clicar...), ele executa cada passo de verdade num navegador visível antes de gravar o node, então dá pra acompanhar a automação sendo construída (e testada) ao vivo, com o editor aberto no mesmo workflow.

MCP é um protocolo aberto — este servidor não tem nada específico de um provedor só, então qualquer cliente MCP funciona (documentado aqui: Claude e Codex, que são os dois já testados).

Ferramentas, arquitetura e limites de design estão documentados em `backend/app/mcp/server.py` e `backend/app/mcp/live_sessions.py`.

## Pré-requisito

O backend precisa estar rodando (`npm run server:dev` na raiz do repo, ou `npm run dev` pra subir backend+frontend juntos). O servidor MCP é montado nele — não é um processo separado.

## Conectando

### Claude Code (CLI)

```bash
claude mcp add --transport http automation http://127.0.0.1:8001/mcp
```

Depois disso, qualquer sessão do Claude Code nesta máquina já enxerga as ferramentas do servidor `automation`.

### Claude Desktop

O Desktop também suporta servidores MCP remotos via HTTP, mas o caminho exato (tela de Configurações → Conectores, ou editar `claude_desktop_config.json` diretamente) muda de versão pra versão — vale conferir a documentação atual do Claude Desktop na hora de configurar, em vez de seguir um passo a passo fixo aqui. O dado que você vai precisar em qualquer caminho é sempre o mesmo: a URL `http://127.0.0.1:8001/mcp`.

### Codex CLI

```bash
codex mcp add automation --url http://127.0.0.1:8001/mcp
```

`codex mcp list` (ou `codex mcp list --json`) confirma que ficou registrado. Sintaxe verificada contra a versão instalada (`codex mcp add --help`) — se um dia mudar, é só rodar esse `--help` de novo.

### Atalho no editor

O topbar do editor (`EditorPage.tsx`) tem um botão (o símbolo do Claude, em laranja) que abre um menuzinho com as opções que chamam `POST /api/launch/terminal` e `POST /api/launch/claude-desktop` (`backend/app/api/launch.py`):

- **Terminal (Claude Code)** / **Terminal (Codex)**: abre uma janela de terminal nova, já dentro da pasta do repo, registra o servidor MCP `automation` automaticamente pro CLI escolhido se ainda não estiver registrado (checado via `claude mcp list` / `codex mcp list --json` antes de tentar de novo) e já inicia uma sessão (`claude "..."` ou `codex "..."`) com um prompt inicial dizendo qual workflow continuar editando (`project_id`/`workflow_id` do editor aberto).
- **Claude Desktop**: só funciona se a variável de ambiente `AUTOMATION_CLAUDE_DESKTOP_CMD` estiver configurada com o comando/caminho que abre o Claude Desktop nesta máquina (ex: o caminho completo do `Claude.exe`) — não existe um caminho de instalação padrão confiável pra chutar, então sem essa variável o botão só explica isso em vez de tentar adivinhar.

O resultado só aparece como um modal quando tem algo relevante pra avisar (erro, ou aviso tipo "MCP não registrado") — um clique que funciona normal não interrompe nada.

**Importante — isso só faz sentido rodando localmente.** Esses endpoints abrem um processo na máquina onde o *backend* está rodando, não na máquina de quem clicou o botão. Hoje isso é a mesma coisa (você roda o backend na sua própria máquina), mas quando este app for pra uma máquina compartilhada da empresa (ver início deste documento), esse botão abriria um terminal *no servidor*, não no notebook de quem clicou — e como o resto da API não tem autenticação, qualquer pessoa na rede poderia acionar esses endpoints pra rodar comando no servidor. Isso foi uma escolha consciente pra manter a conveniência agora; precisa ser revisto (autenticação, ou remover o atalho) antes da mudança pra máquina compartilhada.

## O que dá pra fazer (Claude ou Codex — as ferramentas são as mesmas)

**Autoria** (sempre disponível — só edita o JSON do fluxo, não executa nada):
`get_node_catalog`, `list_projects`, `list_folders`, `list_workflows`, `get_workflow`, `create_workflow`, `add_node`, `connect_nodes`, `update_node`, `delete_node`, `validate_workflow`.

**Execução ao vivo** (abre um navegador real e pausado, executa um passo por vez antes de gravar o node — só pra tipos de node "simples", sem bloco aninhado: navegar, preencher, clicar, passar mouse, selecionar opção, esperar, ler texto, checar elemento, HTTP request sem auto-loop):
`start_live_session`, `demo_node`, `finish_live_session`.

Passos que precisam de laço/condicional (`loop`, `if`) ou de credencial (`browser_2captcha`) continuam sendo criados no fluxo, só que sem execução ao vivo naquele momento — e qualquer node que precisaria de uma credencial que o Claude não tem como escolher vira automaticamente um placeholder (`unknown`) com uma nota explicando o motivo, pra você configurar manualmente no editor depois.

**Fora do escopo, de propósito**: nenhuma ferramenta cria/edita credenciais (só o placeholder acima), nenhuma roda um workflow já pronto (isso continua sendo o botão Run do editor, uma ação manual), e não existe ferramenta pra criar projeto/pasta — se não existir um projeto adequado, o agente vai te pedir pra criar um pela UI primeiro.

## Exemplo

Prompt pro Claude ou Codex (depois de conectado):

> "No projeto DIAS_COSTA_AUTOMACAO, cria uma automação nova chamada 'Login Portal' que abre https://portal-exemplo.com.br, preenche o campo de usuário com 'demo' e clica em Entrar."

Nos bastidores, o Claude tipicamente chama as ferramentas nessa ordem:

1. `get_node_catalog()` — carrega o vocabulário de nodes e as regras estruturais.
2. `list_projects()` — encontra o id do projeto "DIAS_COSTA_AUTOMACAO".
3. `create_workflow(project_id=..., name="Login Portal")` — cria o workflow vazio. Nesse momento você já pode abrir a URL do workflow no editor pra acompanhar.
4. `start_live_session(project_id=..., workflow_id=...)` — abre um Chrome de verdade na tela, pausado. O node **Open Browser** já aparece no canvas.
5. `demo_node(type="goto", params={"url": "https://portal-exemplo.com.br"})` — navega de verdade; se funcionar, o node **Navigate** aparece conectado ao anterior.
6. `demo_node(type="fill", params={"selector": "#username", "value": "demo"})` — preenche de verdade; se o seletor não existir, a ferramenta devolve o erro e nada é gravado — o Claude ajusta o seletor e tenta de novo sozinho antes de te perguntar algo.
7. `demo_node(type="click", params={"selector": "#login-button"})` — clica de verdade; node **Click** aparece.
8. `finish_live_session(...)` — fecha o navegador da sessão de construção.
9. `validate_workflow(...)` — confirma que o fluxo inteiro está estruturalmente correto antes do Claude te avisar que terminou.

Resultado: um workflow real, salvo, com os nodes exatos que você veria se tivesse montado na mão — pronto pra revisar/publicar/rodar pela UI normalmente. Se algum passo não tivesse node correspondente (ex: resolver um captcha), ele apareceria como um node "Unknown" com uma nota explicando o que falta configurar manualmente.

Pra editar esse mesmo fluxo depois, numa conversa nova, é só pedir de novo — o Claude usa `list_workflows`/`get_workflow` pra ver o que já existe e depois `add_node`/`connect_nodes` sobre o workflow existente (a sessão ao vivo, se for chamada de novo, começa com um navegador limpo, sem retomar o login/estado da vez anterior).
