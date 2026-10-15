# Logs e erros

## Onde olhar primeiro

| Sintoma | Onde |
| --- | --- |
| App não abre | Mensagens do checklist no console do `Iniciar AppCaptacao.bat` |
| Relatório `nao_baixado` | Campo **etapa** na tela + log técnico |
| Login do Sienge falha | Log técnico (passo a passo do SSO) |
| Erro "inesperado" na tela | Log técnico: o detalhe técnico nunca vai para a tela |

## Log técnico (arquivo)

`%LOCALAPPDATA%\AppCaptacao\logs\appcaptacao.log` — tudo de `app_captacao.*` a partir de INFO,
com rotação a cada 5 MB: o arquivo atual e mais 5 anteriores (até 30 MB). O console (janela do `Iniciar AppCaptacao.bat`) mostra as
mesmas mensagens com a hora e os marcadores do checklist: `[INFO ]` para as etapas da automação,
`[AVISO]` e `[ERRO ]`. No console cada erro ocupa uma linha (mensagem, tipo e primeira linha do
erro); o traceback completo fica só no arquivo. O `run.py` imprime o caminho do arquivo ao iniciar
("Log tecnico: ..."): com o Python da Microsoft Store o Windows redireciona `%LOCALAPPDATA%` para
`%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.x_...\LocalCache\Local\AppCaptacao`.

## Logs no banco

Pausados por padrão. Com `APP_SAVE_LOGS=true`:

- `CapRecursoLogConfiguracao`: login, logout, criação/edição de usuário e de operação, vínculos e filtros.
- `CapRecursoLogOperacao`: cada execução com entrada, resultado e erros (JSON).

A tela **Logs** lê essas tabelas e exporta em JSON. Com a gravação pausada, a tela fica vazia.

## Etapas de falha de um relatório

| Etapa | O que aconteceu | O que conferir |
| --- | --- | --- |
| `autenticacao` | Navegador não abriu ou login não concluiu (todos ficam `ignorado`) | Credenciais, MFA, Edge instalado |
| `execucao` | Falha na tela do relatório (campo não encontrado, timeout) | Mudança de layout no Sienge; cadastro dos filtros |
| `preenchimento_modal` | Datas do modal do saldo devedor não foram aplicadas | Layout do modal |
| `download` | Nenhum arquivo novo e estável no prazo | Exportação no Sienge, pasta de downloads, `SELENIUM_DOWNLOAD_WAIT_TIMEOUT_SECONDS` |
| `renomeacao` | Arquivo baixado mas não renomeado | Arquivo aberto no Excel, permissões |
| `copia` | Não copiou para o destino | Destino precisa ser pasta sincronizada ou UNC, não link `https://` |

## Mensagens do checklist de inicialização

| Mensagem | Tipo | Correção |
| --- | --- | --- |
| Bibliotecas faltando | ERRO | Abrir pelo `Iniciar AppCaptacao.bat` (instala no `.venv`) |
| Nenhum arquivo de configuração | ERRO | Copiar `.env.example` para `.env` |
| Variáveis obrigatórias vazias | ERRO | Preencher `DB_HOST`, `DB_DATABASE`, `DB_USER`, `DB_PASSWORD` |
| Banco de dados: `Login failed` | ERRO | Usuário/senha SQL incorretos ou expirados |
| Banco de dados: timeout | ERRO | Rede/VPN ou `DB_HOST` |
| FLASK_SECRET_KEY vazia | AVISO | Gerar uma chave; sem ela todos são deslogados a cada reinício |
| APP_HOST=0.0.0.0 | AVISO | App acessível pela rede; use `127.0.0.1` se for uso local |
| Navegador não encontrado | AVISO | Instalar o Edge ou ajustar `SELENIUM_BROWSER` |

## Regras

- Erro técnico nunca aparece como sucesso, e o detalhe técnico (SQL, driver) nunca vai para a tela.
- Mensagem de regra de negócio (`ValueError`) é mostrada ao usuário como está.
- Senha do Sienge e do banco nunca entram em log.
