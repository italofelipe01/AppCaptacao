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
