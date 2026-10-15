# Login no Sienge

A parte mais frágil da automação. Código em
[automacao/login.py](../../src/app_captacao/automacao/login.py),
[automacao/sessao.py](../../src/app_captacao/automacao/sessao.py) e, para a escolha da janela do
Edge, [automacao/navegador.py](../../src/app_captacao/automacao/navegador.py).

E-mail e senha vêm da tela principal (campos `email` e `senha`, não armazenados) e chegam ao login
por `/processar` → `execucao/runner.py` → `automacao.executar_relatorio(s)`.

## Como o login anda

O login não segue passos fixos. A cada ciclo, `identificar_tela` reconhece a tela aberta e o login
age nela, até a sessão ficar estável no Sienge. Só elementos **visíveis** contam: a Microsoft deixa
um campo de senha oculto na tela de e-mail e um de e-mail oculto na tela de senha.

As telas variam conforme o navegador e a máquina. Mapa levantado no Sienge da EBM (out/2026):

| Tela (`TELA_*`) | Como é reconhecida | Ação |
| --- | --- | --- |
| Sienge: entrar | `#btnEntrarComSiengeID` | clica |
| Sienge ID: e-mail | `input[name=email]` | preenche e clica em **Continuar** |
| Sienge ID: escolher conta | `[data-testid=sign-in-v2-choose-account-container]` | clica no usuário atual ou no e-mail lembrado; senão, **Usar outra conta** |
| Sienge ID: senha (conta local) | `input[name=password]` | preenche uma vez e continua |
| Microsoft: escolha uma conta | `#tilesHolder` | clica na conta do e-mail (`[data-test-id]`); senão, `#otherTile` |
| Microsoft: e-mail | `input[name=loginfmt]` visível | preenche e clica em **Avançar** (`#idSIButton9`) |
| Microsoft: senha | `input[name=passwd]` visível | preenche **uma vez** e clica em **Entrar** |
| Microsoft: MFA | `#idDiv_SAOTCAS_Title` / `#idRichContext_DisplaySign` | espera a aprovação; o número vai para o log |
| Microsoft: continuar conectado? | `#KmsiCheckboxField` ou URL `/kmsi` | responde **Não** (`#idBtn_Back`) |
| Sienge: usuário já conectado | link `removerUsuarioLogadoServlet?acao=S` | **Prosseguir**: encerra a outra sessão do usuário |
| Sienge: logado | host do `SIENGE_LOGIN_URL`, página carregada, sem tela de login | 4 confirmações na mesma URL |

Por que as telas mudam:

- **Sienge ID "escolher conta"**: o Sienge ID lembra os e-mails no `localStorage`
  (`remembered-logins`) do perfil do navegador. O perfil da automação é persistente, então a partir
  da segunda execução a tela de e-mail dá lugar à lista de contas.
- **Microsoft "escolha uma conta"**: o Sienge pede `prompt=select_account`. Num Windows ligado ao
  Entra ID, a Microsoft lista a conta do Windows ("Conectado ao Windows") e entra sem senha nem MFA.
  Sem essa ligação aparecem e-mail, senha e MFA.
- **Usuário já conectado**: o Sienge aceita uma sessão por usuário. Se o usuário estiver logado em
  outro navegador, a automação encerra aquela sessão para entrar.

A senha nunca é enviada duas vezes: repetir uma senha recusada pode bloquear a conta no Entra ID.

## Prazos

- Tela sem ação (carregando ou desconhecida): até `max(SELENIUM_DEFAULT_TIMEOUT, 30)` segundos.
- Tela de MFA: até `SELENIUM_MICROSOFT_MFA_WAIT_SECONDS` (padrão 60 s) para a aprovação.
- Cada ação é repetida no máximo 3 vezes na mesma tela (a senha, 1 vez).

## Quando o automático falha

Senha recusada, MFA não aprovado no prazo, tela que não avança ou tela desconhecida (layout novo)
caem no **login interativo**: a mesma janela fica aberta por até
`SIENGE_INTERACTIVE_LOGIN_TIMEOUT_SECONDS` (padrão 180 s) para o usuário concluir à mão. Concluído,
a sessão é salva (se `SIENGE_SESSION_REUSE_ENABLED=true`). Se não concluir, todos os relatórios
ficam `ignorado` na etapa `autenticacao`, com o motivo na mensagem.

## Sessão salva

- Cookies, `localStorage` e `sessionStorage` são gravados cifrados com DPAPI em
  `%LOCALAPPDATA%\AppCaptacao\state\sienge_sessions\`.
- **A sessão salva não é restaurada**: todo login passa pelo fluxo automático. Decisão registrada
  em [DECISIONS.md](../DECISIONS.md) (D6) e protegida por teste.

## Navegador

- Padrão: Edge, anexado por porta de depuração (`SELENIUM_ATTACH_NORMAL_EDGE=true`, porta 9223)
  com perfil exclusivo da automação em `%LOCALAPPDATA%\AppCaptacao\state\edge_automation_profile`.
  O Edge continua aberto entre execuções; com a sessão do Sienge ainda válida, o login termina na
  primeira verificação.
- Ao anexar, o driver escolhe a aba web (de preferência a do Sienge). Num Windows ligado ao Entra
  ID, o perfil novo entra sozinho na conta e abre o diálogo `edge://sync-confirmation-dialog/`, que
  também aparece como janela.
- Janelas: depois do login a aba do Sienge fica guardada como **janela principal**
  (`navegador.definir_janela_principal`). `fechar_janelas_extras` lê a URL de cada janela pelo
  DevTools (`Target.getTargets`), fecha só as abas web abertas pelo relatório e **nunca** toca em
  janela interna (`edge://`, `devtools://`...): tentar fechar o diálogo trava 20 s e pode derrubar a
  sessão do Selenium. A referência é sempre a janela principal guardada, nunca a "janela atual",
  que depois de uma falha pode ser o diálogo. Todos os executores usam essa mesma função.
- Os downloads do Edge anexado são apontados para `SELENIUM_DOWNLOAD_DIR` pelo DevTools
  (`Browser.setDownloadBehavior`); se isso falhar, a execução para com erro claro em vez de baixar
  na pasta padrão do Edge.
- Se a sessão do Selenium cair no meio de uma operação (`invalid session id`), a automação se
  reconecta ao Edge e refaz o login antes do próximo relatório (até 2 vezes por operação).
- Chrome só com `SELENIUM_BROWSER=chrome`. Falha do Edge **não** cai para o Chrome (D5).

## Como diagnosticar

- O log técnico (`%LOCALAPPDATA%\AppCaptacao\logs\appcaptacao.log`) registra cada tela reconhecida
  (`Login Sienge: tela ...`) e cada escolha de conta.
- Uma tela que fica em `carregando` até o prazo indica layout novo: compare o HTML da tela com os
  seletores do mapa acima e ajuste `automacao/login.py`, nunca com exceção por usuário.
- Com `SELENIUM_DEBUG_ARTIFACTS=true`, os executores salvam print e HTML da tela em
  `<pasta de downloads>\_debug_selenium\`.
