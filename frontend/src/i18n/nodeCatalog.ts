// Portuguese overrides for the node catalog's display text (label/description/
// example) — the catalog itself (backend/app/nodes/*.py) stays English-only as the
// canonical, codegen-facing source; this is purely a display-layer translation the
// palette/tooltips/canvas apply on top when the UI language is 'pt'. Keyed by the
// node `type` string exactly as returned by GET /api/node-types.
export interface NodeCatalogText {
  label: string
  description: string
  example: string
}

export const nodeCatalogPt: Record<string, NodeCatalogText> = {
  schedule_trigger: {
    label: 'Gatilho de Agenda',
    description:
      'Inicia este workflow numa agenda recorrente — um intervalo simples (a cada N segundos/minutos/horas/dias) ou uma expressão cron de 5 ou 6 campos (seg min hora dia mês dia-da-semana). Precisa ser o node inicial do workflow. Só roda na agenda enquanto Publicado (botão no topo).',
    example: 'Todo dia às 08:00',
  },
  webhook_trigger: {
    label: 'Webhook',
    description:
      'Inicia este workflow quando uma requisição HTTP chega em /api/webhooks/<path>/<secret>. O secret é gerado automaticamente pra não dar pra adivinhar a URL — use o botão de regenerar pra trocá-lo. Precisa ser o node inicial do workflow, e só dispara enquanto o workflow está publicado (botão no topo) — igual o Gatilho de Agenda.',
    example: 'POST /webhooks/novo-lead',
  },
  http_request: {
    label: 'Requisição HTTP',
    description:
      'Busca dados de uma API. Por padrão já faz o loop direto sobre o resultado (uma iteração por item); desligue "Loop automaticamente" pra em vez disso guardar os dados numa variável nomeada, pra um node Loop separado buscar e iterar depois.',
    example: 'GET https://api.exemplo.com/leads — guarda a resposta JSON numa variável',
  },
  loop: {
    label: 'Loop',
    description:
      'Itera sobre um array — digitado direto como JSON, ou lido de uma variável definida por um node anterior — rodando tudo que vem depois uma vez por item, acessível como {{item.campo}} (mesmo mecanismo do loop da Requisição HTTP).',
    example: 'Itera sobre {{leads}}, rodando os nodes internos uma vez por item',
  },
  open_browser: {
    label: 'Abrir Navegador',
    description: 'Abre o Chrome via Playwright e cria uma nova página.',
    example: 'Abre o Chrome (visível) e uma página em branco',
  },
  browser_2captcha: {
    label: 'Navegador (2Captcha)',
    description:
      'Conecta a um navegador na nuvem via Scraping Browser do 2Captcha em vez de abrir um local — útil quando você quer que a navegação/IP aconteça fora desta máquina. Precisa de uma credencial \'2captcha_browser\' cujo Valor seja \'login:senha\' (do seu painel do 2Captcha Scraping Browser) mais um Profile ID.',
    example: 'Conecta a um Scraping Browser do 2Captcha em vez de um Chrome local',
  },
  close_browser: {
    label: 'Fechar Navegador',
    description:
      'Fecha o navegador aberto pelo Abrir Navegador (equivalente ao quit() do Selenium). Opcional — o navegador já é fechado automaticamente no fim do seu bloco mesmo sem este node; use pra fechar mais cedo, no meio do fluxo.',
    example: 'Fecha o navegador aberto antes neste fluxo',
  },
  switch_frame: {
    label: 'Trocar Frame',
    description:
      'Entra num iframe pelo seletor pras ações seguintes (Preencher, Clicar, Passar Mouse, Selecionar Opção, Esperar, Elemento Presente?). Sempre resolve a partir da página principal primeiro, então nunca fica aninhado dentro de um frame anterior — equivalente a switch_to.default_content() seguido de switch_to.frame(id) do Selenium. Deixe o seletor vazio pra voltar pra página principal.',
    example: "Entra no iframe que bate com '#payment-frame' — nodes seguintes agem dentro dele",
  },
  goto: {
    label: 'Navegar',
    description: 'Navega a página atual pra uma URL.',
    example: 'Navega para https://exemplo.com/login',
  },
  fill: {
    label: 'Preencher Campo',
    description: 'Preenche um campo de texto identificado por um seletor.',
    example: "Preenche '#email' com 'joao@exemplo.com'",
  },
  select_option: {
    label: 'Selecionar Opção',
    description: 'Seleciona uma opção num elemento <select> identificado por um seletor.',
    example: "Seleciona 'Brasil' no <select> '#pais'",
  },
  click: {
    label: 'Clicar',
    description: 'Clica num elemento identificado por um seletor.',
    example: "Clica no botão que bate com '#submit'",
  },
  hover: {
    label: 'Passar Mouse',
    description: 'Passa o mouse sobre um elemento identificado por um seletor.',
    example: "Passa o mouse sobre '.menu-item' pra revelar um submenu",
  },
  multi_input: {
    label: 'Múltiplos Campos',
    description:
      'Preenche ou seleciona vários campos num só passo — adicione uma linha por campo, cada uma com seu próprio seletor, tipo de seletor (ID/Classe/CSS/XPath/XPath Completo), e se é um input de texto ou um select. Roda de cima pra baixo, num único node.',
    example: "Preenche '#nome' com 'Ana' e '#email' com 'ana@x.com' num só passo",
  },
  multi_click: {
    label: 'Múltiplos Cliques',
    description:
      'Clica em vários elementos num só passo — adicione uma linha por elemento, cada uma com seu próprio seletor e tipo de seletor (ID/Classe/CSS/XPath/XPath Completo). Roda de cima pra baixo, num único node, um clique após o outro.',
    example: "Clica em '.tab-1' e depois '.tab-2' em sequência",
  },
  html_list_select: {
    label: 'Selecionar Lista HTML',
    description:
      'Pra menus HTML customizados que não são um <select> de verdade — um elemento gatilho que você clica pra revelar um painel de itens <li>, escolhidos pelo TEXTO visível em vez de um seletor frágil de posição/índice. O modo Dropdown clica uma opção (o menu se fecha sozinho, igual o comportamento do próprio site); o modo Checkbox pode primeiro limpar todo checkbox nativo ou ARIA marcado dentro do painel configurado, depois clica várias opções em sequência sem reabrir o menu entre elas. Um texto ambíguo (mais de um elemento na página contém ele) falha com o erro claro do próprio Playwright em vez de adivinhar — use \'Seletor do Container da Lista\' pra restringir a busca só ao painel do menu quando isso acontecer.',
    example: "Abre o menu 'Status' e clica na opção 'Aprovado'",
  },
  searchable_dropdown_select: {
    label: 'Selecionar Dropdown com Busca',
    description:
      'Seleciona uma opção em um dropdown pesquisável customizado: clica no campo, espera o input de busca visível, digita o texto desejado e confirma com Enter. Os seletores do gatilho e do input são independentes para funcionar com diferentes bibliotecas de interface.',
    example: "Abre o dropdown de modelo, digita 'DADOS DO PROCESSO' e confirma com Enter",
  },
  wait: {
    label: 'Esperar',
    description: 'Pausa a execução por uma duração fixa ou até um elemento aparecer na página.',
    example: "Espera 2 segundos, ou até '#resultado' aparecer na página",
  },
  element_present: {
    label: 'Elemento Presente?',
    description:
      'Verifica se um elemento que bate com um seletor existe atualmente na página (ex: pra detectar se o login deu certo), guardando Verdadeiro/Falso numa variável pra um node SE decidir o caminho depois.',
    example: "Verifica se '#logged-in-badge' existe, guardando Verdadeiro/Falso em 'logado'",
  },
  element_if: {
    label: 'Condição do Elemento',
    description:
      'Junta o Elemento Presente? com o SE num só passo: procura um elemento e, só se ele estiver lá, já verifica uma condição sobre ele (o texto dele ou um atributo) — o ramo verdadeiro só dispara quando o elemento existe E a condição bate. Evita ter que encadear um Elemento Presente? separado antes de um SE só pra checar algo sobre o que foi encontrado.',
    example: "Se '.status-badge' está presente e o texto dele contém 'Aprovado', segue o caminho verdadeiro, senão o falso",
  },
  get_text: {
    label: 'Pegar Texto',
    description:
      'Espera um elemento que bate com um seletor (ID/Classe/CSS/XPath/XPath Completo) aparecer, depois lê o texto visível dele e guarda numa variável, pronta pra referenciar em outro lugar como {{nomeVar}} ou alimentar um node Loop. A espera explícita (com Timeout configurável) protege contra um site lento/instável onde o elemento ainda não renderizou.',
    example: "Espera '#preco' aparecer, depois lê o texto dele na variável 'preco'",
  },
  execute_script: {
    label: 'Executar Script (JS)',
    description:
      'Roda JavaScript puro na página — mesma ideia do execute_script() do Selenium/ChromeDriver: o corpo do script pode referenciar valores passados como arguments[0], arguments[1], ... (veja \'Argumentos\' abaixo), e um `return` vira o resultado deste node. Roda no nível da página (document/window), não restrito ao frame atual do Trocar Frame. O texto do script em si NÃO passa por substituição de template — passe valores dinâmicos pelos Argumentos em vez de montar o script como string, assim nada que você passar quebra a sintaxe do JS sem querer.',
    example: "return document.title;  // resultVar recebe o título da página",
  },
  if: {
    label: 'SE',
    description:
      'Ramifica a execução com base numa condição — escolha um tipo (Texto/Número/Data e Hora/Booleano/Array/Objeto), um operador, e o(s) valor(es) pra comparar, no estilo n8n. Conecte as duas saídas a caminhos separados de verdadeiro/falso — na v1 os ramos rodam de forma independente e não se reúnem.',
    example: "Se {{status}} for igual a 'Aprovado', segue um caminho, senão o outro",
  },
  pause: {
    label: 'Pausa',
    description:
      'Cai no pdb (pdb.set_trace()) bem aqui, pausando o script. Mesmo mecanismo de ativar um breakpoint num conector, mas como um node explícito — use o botão Continuar do painel Run ou digite um comando pdb pra retomar.',
    example: 'Para a execução aqui pra você inspecionar a página com pdb',
  },
  error: {
    label: 'Erro',
    description:
      'Falha a execução de propósito bem aqui: despublica este workflow e marca com um estado de erro vermelho — mostrado tanto no botão Publicar deste workflow quanto na linha dele na lista de workflows — depois levanta uma exceção, então a execução para neste node igual pararia em qualquer outra falha. Diferente de uma falha comum (que só despublica automaticamente numa execução não-assistida por Agenda/Webhook), este node sempre marca o workflow como quebrado, não importa como a execução foi iniciada. Use pra capturar de propósito um caso inesperado/inválido, ex: no fim de um ramo de um node SE.',
    example: "Falha com 'Status de conta inesperado', despublicando este workflow",
  },
  two_captcha: {
    label: '2Captcha',
    description:
      'Resolve um captcha via o serviço 2Captcha e guarda a resposta/token numa variável — reCAPTCHA v2/v3, hCaptcha, Cloudflare Turnstile e FunCaptcha usam a URL atual da página e uma site key; Captcha de Imagem tira um print de um elemento na página e manda pra reconhecimento de texto. Também preenche o token resolvido no campo de resposta oculto da própria página (a menos que desligado) — alguns sites também exigem que seu próprio callback JS seja disparado antes do formulário realmente enviar; se a página ainda não avançar depois deste node, adicione um node Pausa logo depois pra inspecionar o que o widget espera. Precisa de uma credencial de API key do 2Captcha.',
    example: "Resolve o reCAPTCHA v2 da página e guarda o token em 'captcha_token'",
  },
  totp: {
    label: 'Código 2FA (TOTP)',
    description:
      'Gera o código atual de 2FA/TOTP (via pyotp) a partir de um secret guardado como credencial — registre o T2FA_SECRET do site como Credencial primeiro (qualquer nome de Tipo, ex: "totp"), depois escolha ela aqui. Guarda o código de 6 dígitos numa variável, pronto pra preencher no formulário de login.',
    example: 'Gera o código atual de 6 dígitos a partir do secret de 2FA guardado',
  },
  save_files: {
    label: 'Salvar Arquivos',
    description:
      'Decodifica um ou mais valores base64 (tipicamente a resposta "File" de um node Requisição HTTP) e escreve em data/projects/<projeto>/temp_files/<este workflow>/<esta execução>/<nome do arquivo> — cada execução ganha sua própria subpasta isolada, então duas execuções disparando ao mesmo tempo nunca misturam os arquivos uma da outra. Pode opcionalmente juntar tudo que foi salvo num arquivo final (zip ou PDF) na mesma pasta. Use Pegar Arquivo em qualquer outro lugar da MESMA execução pra recuperar o que foi salvo aqui pelo nome do arquivo.',
    example: "Decodifica um PDF em base64 de uma Requisição HTTP anterior e salva como 'fatura.pdf'",
  },
  get_file: {
    label: 'Pegar Arquivo',
    description:
      'Busca um arquivo pelo nome dentro da pasta temp_files deste workflow (o que um node Salvar Arquivos já escreveu antes nesta execução) e guarda o caminho numa variável — não precisa estar conectado direto ao node Salvar Arquivos, pode ficar em qualquer lugar depois no fluxo. Alimente o resultado no Enviar Arquivo pra anexar a um input de arquivo, ou referencie em qualquer campo com template.',
    example: "Busca 'fatura.pdf' salvo antes nesta execução e guarda o caminho em 'caminhoArquivo'",
  },
  upload_file: {
    label: 'Enviar Arquivo',
    description:
      'Anexa um arquivo a um input de arquivo (<input type="file">) identificado por um seletor — o equivalente do Preencher Campo pra campos de texto. Caminho do Arquivo costuma ser {{nodePegarArquivo.resultVar}} de um node Pegar Arquivo, ou {{nodeSalvarArquivos.resultVar.files[0]}} direto do Salvar Arquivos.',
    example: "Anexa 'caminhoArquivo' ao input de arquivo '#upload'",
  },
  download_file: {
    label: 'Baixar Arquivo',
    description:
      'Clica num elemento que dispara um download no navegador, espera terminar, e salva direto na pasta temp_files deste workflow (nunca na pasta Downloads do sistema) — pronto pro Pegar Arquivo/Enviar Arquivo em outro lugar da MESMA execução. Precisa de um Abrir Navegador antes no fluxo. O nome do arquivo por padrão é o que o servidor sugeriu; defina Nome do Arquivo pra renomear. Nunca sobrescreve um arquivo existente silenciosamente — adiciona um sufixo numerado a menos que Sobrescrever esteja ligado. Cada execução ganha sua própria subpasta isolada, então duas execuções deste workflow disparando ao mesmo tempo (ex: duas chamadas de webhook, ou uma execução agendada sobrepondo uma manual) nunca misturam os arquivos uma da outra.',
    example: "Clica em '.download-link' e salva o arquivo baixado",
  },
  save_cookies: {
    label: 'Salvar Cookies',
    description:
      'Salva os cookies do contexto atual do navegador (sessões de login, etc.) — persiste entre execuções, então um node Carregar Cookies posterior (nesta execução ou numa futura) pode pular o fluxo de login inteiro. Precisa de um Abrir Navegador antes no fluxo. Diferente do Salvar Arquivos/Baixar Arquivo, isso NÃO é isolado por execução — salvar sobrescreve o que já estava lá, de propósito. Escolha uma Credencial pra salvar no MESMO jar compartilhado que um node Login/Login Microsoft (ou o Salvar Cookies de outro workflow) usa pra essa credencial — qualquer outro workflow pode depois carregar via Carregar Cookies apontando pra mesma credencial. Deixe em branco pra salvar no jar próprio deste workflow por nome de arquivo, como antes.',
    example: 'Salva os cookies da sessão de login atual, compartilhado por credencial ou restrito a este workflow',
  },
  load_cookies: {
    label: 'Carregar Cookies',
    description:
      'Carrega cookies escritos antes por um node Salvar Cookies, ou por um node Login/Login Microsoft, no contexto atual do navegador — coloque logo após o Abrir Navegador e antes de navegar, pra o site ver os cookies de sessão já na primeira requisição. Na primeiríssima execução (ainda sem arquivo de cookies) ele só pula o carregamento e registra isso no log, a menos que "Pular se não existir" esteja desligado. Precisa de um Abrir Navegador antes no fluxo. Escolha uma Credencial pra carregar o jar compartilhado que um node Login/Login Microsoft (ou o Salvar Cookies de outro workflow) salvou pra essa credencial — é isso que permite um workflow DIFERENTE reaproveitar uma sessão sem ter seu próprio node Login. Deixe em branco pra carregar do jar próprio deste workflow por nome de arquivo, como antes.',
    example: 'Carrega uma sessão salva antes, compartilhada por credencial ou restrita a este workflow',
  },
  login: {
    label: 'Login',
    description:
      'Um fluxo de login completo num único node: a menos que "Reaproveitar sessão salva" esteja desligado, carrega primeiro qualquer cookie salvo numa execução anterior e verifica se o elemento de confirmação já está lá (pula o formulário inteiro se sim); senão preenche usuário/senha de uma credencial, envia, opcionalmente lida com uma etapa de 2FA TOTP, espera o elemento de confirmação pra provar que funcionou, depois salva cookies novos pra próxima vez — o salvamento acontece sempre que um login de verdade dá certo, independente dessa opção. Precisa de um Abrir Navegador antes no fluxo. Não lida com captchas — se o formulário de login tiver um, adicione um node 2Captcha entre preencher a senha e clicar em enviar. O jar de cookies é vinculado à própria Credencial de Login (não a este workflow) — qualquer outro workflow que use a mesma credencial, seja pelo próprio node Login ou por um node Salvar Cookies/Carregar Cookies apontando pra essa credencial, compartilha a mesma sessão salva.',
    example: 'Faz login em https://app.exemplo.com usando uma credencial guardada, depois salva a sessão',
  },
  microsoft_login: {
    label: 'Login Microsoft',
    description:
      'Entra pelas páginas de usuário/senha em duas etapas da Microsoft usando uma credencial de login do projeto, depois salva cookies pra execuções futuras. Use um seletor de confirmação que só exista dentro do app de destino. O jar de cookies é vinculado à própria credencial (não a este workflow) — qualquer outro workflow que use a mesma credencial compartilha a mesma sessão salva.',
    example: "Entra numa página de login Microsoft/Office 365 (usuário + senha, 'permanecer conectado' opcional)",
  },
  unknown: {
    label: 'Desconhecido (de importação)',
    description:
      'Espaço reservado pra um trecho de código de um arquivo Python importado que não bateu com nenhum tipo de node existente. Guarda o trecho original palavra por palavra — ainda roda exatamente como antes — então o workflow reconstruído funciona imediatamente. Substitua por um node tipado de verdade quando puder.',
    example: 'Um espaço reservado pra um passo que este app ainda não tem um node',
  },
}
