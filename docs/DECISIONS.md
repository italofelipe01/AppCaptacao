# Decision Log

Decisões arquiteturais e trade-offs aceitos. Formato: contexto, decisão, consequência.

## D1 — Versões anteriores preservadas só no git (2026-10-14)

- **Contexto:** `oldversion/` (336 MB) guardava duas versões anteriores com executáveis e `.env` reais.
- **Decisão:** as duas versões viraram os primeiros commits (`chore(legado)`), sem segredos,
  builds nem executáveis, e a pasta foi apagada. Valores reais achados no código e no manual
  antigos foram trocados por marcadores antes do commit.
- **Consequência:** `git log` mostra a evolução completa. O `FLASK_SECRET_KEY` real estava fixo
  no código e no manual da primeira versão: tratar como exposto e trocar.

## D2 — Código em `src/app_captacao/` por responsabilidade (2026-10-14)

- **Contexto:** `app_core/app.py` (2305 linhas) e `services/automacao_service.py` (2543 linhas)
  misturavam rotas, SQL, autenticação, jobs e Selenium.
- **Decisão:** camadas `core`, `catalogo`, `automacao`, `execucao`, `web`, `desktop`, no modelo
  do portal-contabilidade. Funções copiadas literalmente; só nomes cruzando módulos mudaram.
- **Consequência:** HTML das páginas e mapa de rotas conferidos idênticos ao estado anterior.

## D3 — Frontend intocado e endpoints sem Blueprint

- **Decisão:** `project/templates` e `project/static` ficam onde estão. Rotas são registradas
  por `RegistroRotas`, mantendo o endpoint igual ao nome da função.
- **Consequência:** `url_for(...)` e `request.endpoint` dos templates continuam funcionando.
  Única mudança em template: valores do backend para o JS passam por bloco JSON (D11).

## D4 — Remoção de código sem uso

- **Decisão:** removidos o motor genérico de filtros (24 funções inalcançáveis, ~800 linhas), o
  mecanismo de "botões automáticos" (lista vazia), `playwright_auth_service.py` e
  `desktop_backend.py`, e as dependências `playwright` e `tkcalendar`.
- **Consequência:** todos os relatórios passam por executor dedicado. O código removido está no
  histórico do git se for preciso consultar.

## D5 — Edge sem fallback para Chrome

- **Decisão:** o navegador é escolhido só por `SELENIUM_BROWSER`; falha do Edge é falha.
- **Consequência:** evita automação rodando em um perfil/navegador inesperado. Protegido por teste.

## D6 — Sessão do Sienge salva, mas não restaurada

- **Decisão:** depois de login interativo os cookies são salvos (DPAPI), mas todo login usa o
  fluxo automático.
- **Consequência:** o motivo não foi registrado na versão anterior; o comportamento já era exigido
  pelo teste `test_login_delegates_to_automatic_flow` e foi mantido. `SIENGE_SESSION_REUSE_ENABLED`
  controla só o salvamento. Religar a restauração exige spec.

## D7 — Configuração carregada antes de qualquer leitura de variável

- **Contexto:** o serviço de automação lia `os.getenv` no import, antes do `.env` ser carregado;
  no executável, valores do configurador eram ignorados.
- **Decisão:** variáveis só são lidas em `core/config/settings.py` e `automacao/config.py`, que
  carregam o `.env` primeiro. `initialize_environment` é idempotente. Em desenvolvimento o `.env`
  da raiz tem prioridade.
- **Consequência:** teste de fronteira impede leitura de `os.getenv` no import fora desses módulos.

## D8 — Banco é a fonte de verdade do usuário logado

- **Decisão:** a cada requisição o usuário é recarregado do banco; inativo ou excluído perde a
  sessão; o perfil vem do banco. Com o banco indisponível, a sessão assinada é aceita.
- **Consequência:** uma consulta por requisição (arquivos estáticos excluídos). Admin local de
  desenvolvimento exige hash de senha.

## D9 — Autenticação de rede Windows mantida, mas não ligada

- **Contexto:** `core/security/network_auth.py` (LogonUser) existe desde a versão anterior, mas
  nunca foi chamado pelo `/login`.
- **Decisão:** mantido isolado e documentado; ligar ao login exige spec (provisionamento de
  usuário sintético e perfil padrão).

## D10 — Executor do saldo devedor mantido em um arquivo

- **Decisão:** `extrato_saldo_devedor_presente.py` passa de 500 linhas, mas não foi dividido.
- **Consequência:** dívida técnica registrada; dividir só com testes cobrindo o fluxo de paginação
  e consolidação.

## D11 — Dados do backend para o JS por bloco JSON

- **Contexto:** `const x = {{ valor|tojson }};` dentro do `<script>` gerava erros falsos no editor.
- **Decisão:** valores vão em `<script type="application/json">` lidos com `JSON.parse`.
- **Consequência:** mesmo comportamento; teste roda `node --check` nos scripts renderizados.

## D12 — Inicialização com checklist

- **Decisão:** `Iniciar AppCaptacao.bat` cria o `.venv` e o `run.py` confere bibliotecas,
  configuração, navegador, pasta de downloads e banco antes de abrir o app. Instalação automática
  só dentro de ambiente virtual.
- **Consequência:** problemas de ambiente aparecem com orientação antes de abrir o navegador.

## D13 — Logs persistidos no banco pausados

- **Contexto:** herdado: `APP_SAVE_LOGS=false` por padrão.
- **Decisão:** mantido; o log técnico em arquivo cobre o diagnóstico.
- **Consequência:** a tela Logs fica vazia até `APP_SAVE_LOGS=true`.

## D14 — Login do Sienge reconhece a tela em vez de seguir passos fixos (2026-10-15)

- **Contexto:** o login esperava sempre e-mail → `loginfmt` → senha. Mapeado no Sienge real: a
  partir da 2ª execução o Sienge ID mostra a lista de contas lembradas; num Windows ligado ao Entra
  ID a Microsoft mostra "escolha uma conta" e entra sem senha; o Sienge pede para encerrar a sessão
  aberta em outro navegador. O código antigo perdia minutos nessas telas e chegava a dar o login por
  concluído na lista de contas do Sienge ID.
- **Decisão:** `login.py` identifica a tela a cada ciclo e age nela, só com elementos visíveis.
  Usuário já conectado → **Prosseguir** (encerra a outra sessão do mesmo usuário). A senha é
  enviada no máximo uma vez. Sessão ativa exige o host do `SIENGE_LOGIN_URL`.
- **Consequência:** tela nova do Sienge/Microsoft vira `carregando` e cai no login interativo com o
  nome da tela no log; o mapa de seletores fica em `docs/processos/login_sienge.md`.

## D15 — Inicializador portátil e janela que mostra tudo (2026-10-15)

- **Contexto:** o projeto foi levado em `.zip` com o `.venv`, que guarda o caminho do Python do
  computador de origem e não abre em outro. O `.bat` só checava se o `python.exe` existia. A janela
  fechava sozinha no fim normal e o console mostrava só avisos e erros.
- **Decisão:** o `.bat` testa o Python do `.venv` e o recria se não rodar, usa `pushd` (pasta na
  rede), numera as etapas e sempre espera uma tecla no fim, com o resultado (OK ou ERRO). O
  console do log técnico passa a mostrar INFO com hora e os marcadores do checklist.
- **Consequência:** a mesma pasta funciona em qualquer computador com Python 3.11+; as etapas da
  automação ficam visíveis na janela, além do arquivo de log.

## D16 — Uma função de janelas para todos os executores no Edge anexado (2026-10-15)

- **Contexto:** num teste real de 7 relatórios, só o primeiro arquivo foi baixado e nenhum foi
  dado como baixado. Com o Edge anexado pela porta de depuração (desde a versão intermediária), o
  driver enxerga o diálogo interno `edge://sync-confirmation-dialog/`. Cada executor tinha sua
  cópia de `_fechar_janelas_extras`, que tentava fechá-lo: travava 20 s, falhava, deixava o driver
  no diálogo, e o relatório seguinte tratava o diálogo como janela principal, fechava a aba do
  Sienge e matava a sessão (`invalid session id`). A primeira versão não tinha o problema porque
  abria um Edge próprio do Selenium.
- **Decisão:** uma só `navegador.fechar_janelas_extras`, usada por todos os executores: lê a URL
  das janelas pelo DevTools, nunca toca em janela interna e usa como referência a aba do Sienge
  guardada depois do login. A operação reconecta ao Edge e refaz o login se a sessão cair (até 2
  vezes). Falha ao apontar os downloads do Edge anexado para `SELENIUM_DOWNLOAD_DIR` passa a ser
  erro. A tela mostra cada arquivo salvo durante a execução e a pasta no resultado.
- **Consequência:** `tests/automacao/test_lote_edge_anexado.py` reproduz a operação do teste real
  e falha contra a lógica antiga.

## D17 — Fechar o Edge anexado no fim da execução (2026-10-16)

- **Contexto:** depois de baixar os relatórios, a página do Sienge ficava aberta. Com o Edge
  anexado pela porta de depuração (D16), `driver.quit()` só desconecta o msedgedriver; quem fechava
  o navegador era o Selenium, quando o Edge era dele. Confirmado num Edge real: depois do `quit()` a
  porta de depuração segue aberta.
- **Decisão:** `navegador.encerrar_driver` manda `Browser.close` pelo DevTools antes do `quit()`,
  só para drivers anexados ao Edge da automação (perfil exclusivo, nunca o Edge pessoal). Chrome
  anexado pode ser o perfil pessoal e continua só desconectado. Quando a sessão cai no meio da
  operação, o driver é só desconectado, porque o mesmo Edge é reanexado. Falha no `Browser.close` vai
  para o log e não muda o resultado.
- **Consequência:** a próxima execução abre um Edge novo e refaz o login, com MFA se a Microsoft
  pedir. Quem preferir manter a sessão entre execuções usa `SELENIUM_KEEP_BROWSER_OPEN=true`.

## D18 — Pasta por relatório e consolidado conferido com o Sienge (2026-10-16)

- **Contexto:** uma operação real com 7 relatórios e 3 empresas deixou 58 arquivos misturados
  numa pasta, cada um duas vezes: o destino era a própria pasta de downloads e a cópia caía ao
  lado do original com `_2`. O nome não identifica o empreendimento (a empresa 242 tinha três), e
  juntar os arquivos exigia limpar à mão o layout de impressão do Sienge.
- **Decisão:** cada arquivo vai para `<base>\<Relatório>\`; com a base igual à pasta de downloads
  ele é movido, não copiado. No fim da execução, o runner chama `consolidacao/`, que lê cada
  arquivo pelo layout do relatório (7 executores com arquivo real visto), confere a soma ou a
  contagem com os totais impressos pelo Sienge (tolerância de R$ 0,005 por linha, o
  arredondamento da exportação) e grava `<Relatório>_consolidado_<data>.xlsx` com as abas Dados,
  Origem e Conferência. Divergência não gera consolidado, e o relatório continua `baixado`.
  `consolidacao/` só depende de `core/`; as regras de nome foram para `core/shared/arquivos.py`.
- **Consequência:** nos 29 arquivos reais, os 7 consolidados saíram com as 65 conferências
  batendo. Quem lia a raiz de `Automação CAP` passa a ler as subpastas. Os outros 10 executores
  precisam de um arquivo real antes de ganhar layout. `APP_CONSOLIDAR_RELATORIOS=false` desliga a
  consolidação. `tests/conftest.py` aponta a pasta de downloads para uma pasta temporária: sem
  destino, os testes moveriam arquivos para a pasta real do usuário.

## D19 — CSS de utilitários gerado a partir dos templates (2026-10-16)

- **Contexto:** `tailwind-local.css` era escrito à mão imitando o Tailwind. Das classes usadas nos
  templates, 21% não existiam nele e o navegador as ignorava sem aviso: login com metade vazia,
  indicador de andamento com 0×0 px, menu com fundos brancos e textos invisíveis (1:1) no tema
  escuro, indicadores empilhados. O reset não zerava o fundo de `<button>` (cinza do Edge) e o
  logo azul-marinho ficava sobre placa escura.
- **Decisão:** o arquivo é gerado pelo Tailwind v3.4.17 standalone (sem Node; SHA-256 fixado em
  `scripts/gerar_css.ps1`) a partir dos templates e do JS estático. v3 porque as cores do arquivo
  antigo eram as da paleta v3 (o v4 recalcula a paleta). Sem o preflight: o reset é o do arquivo
  antigo mais borda padrão, fundo transparente em botão e `fieldset` sem margem; o preflight zeraria
  as margens de textos e mudaria o espaçamento de todas as telas. O logo usa `.logo-placa` (fundo
  branco nos dois temas). Onde o arquivo antigo clareava de propósito (`dark:text-slate-500` com a
  cor do slate-400), o template passou a usar a classe da cor que já aparecia.
- **Consequência:** `tests/web/test_css_gerado.py` falha quando uma classe dos templates fica sem
  regra (lembrar de rodar o script). No escuro, as falhas de contraste medidas caíram de 33 para
  10. No login, o botão de tema foi para o canto do cartão para o Entrar continuar visível num
  notebook 1366×768 (o espaçamento que passou a valer o empurrava 62 px para baixo).

## D20 — Estrutura das telas e modais num script só (2026-10-16)

- **Contexto:** medido nas áreas úteis reais do Edge, o andamento da execução começava em
  y=1201 (abaixo do formulário), o menu levava Tema e Sair para o fim da página, os botões das
  tabelas empilhavam e a coluna Ações de Usuários sumia a partir de 1366. Usuários e Operações
  tinham cada um a sua cópia de `abrirModal`/`fecharModal`. Nelas o foco não entrava no modal, Esc
  fechava tudo (até na busca do combobox) e Esc ou clique fora descartavam o que foi digitado.
- **Decisão:** o menu é `sticky` na altura da janela, e só a lista do meio rola. O estado
  recolhido é aplicado por um script logo depois do `<aside>`, antes da primeira pintura. Na tela
  de execução, o andamento e o resultado vêm antes do formulário, e só o resumo é `aria-live`.
  O comportamento de modal fica em `project/static/js/modal.js`, carregado pelo layout:
  - o foco vai para o primeiro campo e volta para quem abriu;
  - o Tab fica preso no modal;
  - Esc e clique fora fecham o modal de cima, com confirmação se algo mudou.

  Os templates não redefinem essas funções. Um componente dentro do modal que use Esc (o combobox)
  chama `stopPropagation`.
- **Consequência:** `tests/web/test_estrutura_frontend.py` cobre rótulos, `autocomplete` das senhas,
  a ordem da tela de execução, `aria-live`, títulos dos modais e o script único. Foco, Tab e Esc
  foram conferidos no Edge, porque não há navegador nos testes. Para as ações caberem em 1280, as
  células das duas tabelas usam 16 px de respiro lateral abaixo de 1536 px, e "Adicionar
  relatorios" virou "Relatórios". O leitor de CSS do teste de classes passou a decodificar escape
  hexadecimal (`.\32xl\:px-6`).

## D21 — Textos com acento e valores gravados pelo nome (2026-10-16)

- **Contexto:** as telas e as mensagens das rotas misturavam texto acentuado com "execucao",
  "relatorio" e "Usuario ou senha invalidos". Parte do texto contradizia o sistema: "sessão
  protegida, reutilizada", "conta corporativa", Logs "assim que o banco for conectado". Áreas,
  eventos, status e estados apareciam pelo código gravado. Na medição, 28 textos ficavam abaixo da
  WCAG AA no claro e 10 no escuro, entre eles o "EBM" do menu, com 1,36:1.
- **Decisão:**
  - **Acentos:** o texto exibido usa português com acentos. Isso vale para os templates, os
    `flash` das rotas, os detalhes da auditoria, os `ValueError` de regra de negócio que vão para
    a tela, os resumos do job e o rótulo dos perfis.
  - **Códigos:** códigos gravados viram nome por `project/templates/components/rotulos.html`,
    importado nas telas. Os valores enviados ao backend e gravados no banco não mudam.
  - **Nome do app:** é "AppCaptação" no menu, no login e no título das abas.
  - **Logs vazios:** a tela recebe `logs_gravados` (`APP_SAVE_LOGS`) para dizer por que a lista
    está vazia.
  - **Mensagens dos executores:** ficaram de fora. Elas descrevem a tela do Sienge e mudam
    junto com os seletores.
- **Consequência:** `tests/web/test_textos_frontend.py` procura palavras sem acento no texto
  visível. Os testes que conferiam mensagem foram atualizados, e o que conferia a ausência do
  sucesso passou a conferir o texto novo, para não passar sempre. Registros de log antigos mantêm
  o texto da época. Valor sem nome na tabela aparece cru.

## D22 — Fechar a janela do relatório só depois do download (2026-10-16)

- **Contexto:** numa operação real, o Extrato cliente histórico (empresa 242, centro de custo
  1002) parou no primeiro arquivo. De manhã, o mesmo filtro tinha entregado o arquivo em 7 s.
  Os executores davam ENTER, esperavam 5 s fixos e fechavam a janela `please_wait_frame.jsp`
  antes de esperar o arquivo. Desta vez o Sienge demorou mais que isso, a janela foi fechada com o
  pedido ainda pendente, e o download nunca começou. A automação ficou 600 s esperando, sem nada
  no log, e o relatório inteiro seria dado como não baixado.
- **Decisão:** os 15 executores que exportavam assim esperam o arquivo (`renomear_download`) e só
  então fecham a janela, como o Quadro espelho já fazia. Quando o download falha, a janela fica
  aberta até `_executar_relatorio_no_driver` fechá-la, antes do próximo relatório.
- **Consequência:** `tests/automacao/test_executores.py` falha se algum executor fechar a janela
  antes de esperar o arquivo. O teste confere a ordem no código de todos os executores e executa
  o Extrato com dublês. A espera fixa depois do ENTER continua, mas deixou de decidir se o
  download dá certo.

## D23 — Filtro do cadastro nunca é descartado em silêncio (2026-10-20)

- **Contexto:** o "Posição em" do Unidades estava cadastrado e chegava ao executor, que o
  ignorava: os arquivos de 16/10 saíram com a data do dia. Os 17 executores procuram uma lista
  fixa de filtros e descartam o resto, e nada amarrava o filtro do app ao campo da tela do Sienge.
  A leitura das 16 telas achou mais casos: "Posição em" do Extrato cliente histórico e "Correção
  até" do Analítico de apropriações ignorados; Unidades e Quadro espelho procurando campos que a
  tela não tem; Empreendimento do Unidades opcional no app, mas exigido pelo Sienge.
- **Decisão:** `catalogo/campos_sienge.py` declara, por executor, os campos da tela (rótulo, id,
  tipo, obrigatório, padrão) e como cada um reconhece o filtro. Os executores continuam com a
  busca deles (reescrever 17 executores arriscaria o que funciona), e
  `tests/catalogo/test_campos_sienge.py` exige que declaração e código procurem exatamente os
  mesmos identificadores e nomes, com a mesma regra de busca. Filtro sem campo vira aviso na
  mensagem do relatório e no log; com `APP_RECUSAR_FILTROS_SEM_CAMPO=true`, a execução é recusada
  antes de abrir o Sienge. Filtro só é opcional quando a tela não o exige (ou traz padrão) e o
  executor aceita vazio sem apagar o padrão.
- **Consequência:** a recusa começa desligada porque o cadastro não pôde ser lido (banco fora do
  ar): ligar antes de auditar pararia operações com filtro hoje ignorado. A auditoria
  (`tools/auditar_filtros_sienge.py`) lê as telas e, com banco, o cadastro, e grava
  `docs/auditoria-filtros-sienge.md`. Campo novo num executor exige a declaração no mesmo commit.

## D24 — Aba Parâmetros no consolidado (2026-10-20)

- **Contexto:** quem recebe o consolidado não tem acesso ao app e não sabia com quais filtros a
  extração foi feita; a aba Dados só tem os campos que o Sienge imprime no cabeçalho, que variam
  por relatório.
- **Decisão:** o consolidado ganha a aba **Parâmetros**, logo depois de Dados, com Filtro, Campo no
  Sienge, Valor usado e Observação, montada dos filtros que a automação recebeu naquela execução.
  As linhas saem de `catalogo/parametros.py` (onde está a declaração dos campos) e chegam à
  consolidação já em texto, mantendo a fronteira 7.
- **Consequência:** filtro não aplicado aparece marcado na aba em vez de sumir. A aba é gravada
  junto com o consolidado: se a conferência falha, nada é gravado, como antes.
