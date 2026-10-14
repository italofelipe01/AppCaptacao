# Login no Sienge

A parte mais frágil da automação. Código em
[automacao/login.py](../../src/app_captacao/automacao/login.py) e
[automacao/sessao.py](../../src/app_captacao/automacao/sessao.py).

## Fluxo automático

1. Abre `SIENGE_LOGIN_URL` (padrão `https://ebm.sienge.com.br/sienge/`).
2. Clica em **Entrar com Sienge ID** (`#btnEntrarComSiengeID`).
3. Preenche o e-mail no primeiro campo que aparecer: `email` ou `username`, e clica em **Continuar**.
4. Se a tela da Microsoft aparecer (`loginfmt`), preenche o e-mail de novo e avança.
5. Preenche a senha (`passwd`, `password` ou `input[type=password]`) e clica em **Entrar**
   (`#idSIButton9`); sem o botão, tenta um botão alternativo e, por fim, ENTER.
6. Espera `SELENIUM_MICROSOFT_MFA_WAIT_SECONDS` (padrão 60 s) para o MFA/token.
7. Se aparecer "Continuar conectado?", responde **Não** (`#idBtn_Back`).
8. Exige sessão estável: 4 confirmações seguidas na mesma URL do domínio Sienge, página carregada
   e nenhum controle de login na tela.

## Quando o automático falha

Qualquer falha do fluxo acima (frame do SSO desanexado, campo ausente, MFA não concluído) cai no
**login interativo**: a mesma janela fica aberta por até `SIENGE_INTERACTIVE_LOGIN_TIMEOUT_SECONDS`
(padrão 180 s, nunca menos que a espera do MFA) para o usuário concluir o login e o token à mão.
Concluído, a sessão é salva (se `SIENGE_SESSION_REUSE_ENABLED=true`).

## Sessão salva

- Cookies, `localStorage` e `sessionStorage` são gravados cifrados com DPAPI em
  `%LOCALAPPDATA%\AppCaptacao\state\sienge_sessions\`.
- **A sessão salva não é restaurada**: todo login passa pelo fluxo automático. Decisão registrada
  em [DECISIONS.md](../DECISIONS.md) (D6) e protegida por teste.

## Navegador

- Padrão: Edge, anexado por porta de depuração (`SELENIUM_ATTACH_NORMAL_EDGE=true`, porta 9223)
  com perfil exclusivo da automação em `%LOCALAPPDATA%\AppCaptacao\state\edge_automation_profile`.
- Chrome só com `SELENIUM_BROWSER=chrome`. Falha do Edge **não** cai para o Chrome (D5).

## Como diagnosticar

- O passo a passo fica no log técnico (`%LOCALAPPDATA%\AppCaptacao\logs\appcaptacao.log`).
- Com `SELENIUM_DEBUG_ARTIFACTS=true`, os executores salvam print e HTML da tela em
  `<pasta de downloads>\_debug_selenium\`.
- Mudança de layout do SSO ou do Sienge exige ajuste nos seletores deste módulo, nunca uma
  exceção por usuário.
