# AppCaptação — Guia para o Claude

Contexto operacional deste repositório. Leia antes de propor código, investigar bug ou desenhar
feature. As regras completas estão em `docs/AI_CONTRACT.md`, `docs/ARCHITECTURE.md`,
`docs/projectmap.md` e `docs/DECISIONS.md`.

## O que é

Aplicação Python para Windows que automatiza o download de relatórios do Sienge. Uma interface
web local (Flask + Waitress em `127.0.0.1:4732`) dispara uma automação Selenium no Edge: login
Sienge ID + SSO Microsoft com MFA, preenchimento de filtros por **executor dedicado** de cada
relatório, exportação, monitoramento do download, renomeação e cópia para pasta sincronizada.
Relatórios, filtros, operações e usuários vivem no **SQL Server** (tabelas `CapRecurso*`).

## Stack e runtime

- Python **3.11+** (desenvolvido em 3.13), Flask, Waitress, Selenium, pyodbc (fallback pymssql),
  openpyxl, CustomTkinter (janelas do `.exe`), pywin32, python-dotenv. PyInstaller para os executáveis.
- Só Windows: configuração cifrada com DPAPI e janelas desktop.
- Configuração por variáveis de ambiente. `.env.example` é a lista canônica; leitura só em
  `core/config/settings.py` e `automacao/config.py`, que carregam o `.env` antes.
- Shell primário: PowerShell. Ambiente do projeto: `.venv` (criado pelo `Iniciar AppCaptacao.bat`).

## Comandos

```powershell
.\Iniciar AppCaptacao.bat                                    # duplo clique: .venv + checklist + app
.\.venv\Scripts\python.exe run.py                            # checklist e app
.\.venv\Scripts\python.exe run.py --somente-verificar        # só o checklist
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest                         # ~70 testes, sem rede/banco
.\.venv\Scripts\python.exe -m compileall -q src tests run.py
npx pyright@1.1.414 --pythonpath .venv\Scripts\python.exe    # deve dar 0 erros
node --check project\static\js\menu.js
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\gerar_executaveis.ps1 -Limpar
```

## Mapa do código

```text
src/app_captacao/
├── app.py                   Flask: before_request (usuário do banco), registro das rotas
├── core/                    base — nunca importa das camadas abaixo
│   ├── config/              environment.py (.env, caminhos), dpapi.py, settings.py
│   ├── database/            connection.py (DbConnection), sql.py (execute/fetch/column_exists)
│   ├── security/            auth.py, perfis.py, sessao_usuario.py, network_auth.py (não ligado)
│   ├── persistence/         usuarios.py, logs.py
│   └── shared/              texto.py, navegador_local.py, log_tecnico.py
├── catalogo/                relatorios.py, regras.py (executor por ID/URL/nome), operacoes.py,
│                            operacao_relatorios.py — SQL e regras do catálogo
├── automacao/               config, navegador, login, sessao, campos, downloads, erros, execucao
│   └── relatorios/          registro.py + executores/<relatorio>.py (17)
├── execucao/                jobs.py (estado em memória por sessão), runner.py (thread)
├── inicializacao/           checklist do run.py (dependencias.py só usa stdlib)
├── web/                     routes_*.py, registro.py (RegistroRotas), erros.py, auditoria.py
└── desktop/                 desktop_app.py (.exe), config_installer.py (configurador)
project/                     FRONTEND (templates + static) — não mudar sem pedido explícito
tests/                       espelha src/; tests/fakes.py tem os dublês de banco
packaging/ scripts/ tools/ docs/
```

## Fronteiras invioláveis

1. `core/` não importa de `catalogo/`, `automacao/`, `execucao/`, `web/`.
2. `catalogo/` não importa de `automacao/`, `execucao/`, `web/`.
3. `automacao/` não importa de `execucao/` nem `web/`.
4. Rotas não escrevem SQL; persistência não lê `flask.g` (usuário vem por parâmetro).
5. `os.getenv` no import só em `settings.py`, `automacao/config.py` e `environment.py`.
6. Endpoints sem Blueprint: o nome da função é o endpoint que os templates usam.
7. Frontend (`project/`) é contrato: rotas, nomes de campo de formulário e endpoints não mudam.
8. Senha do Sienge nunca é gravada; `.env`, `.config/` e `*.env.enc` nunca entram no git.

`tests/test_fronteiras.py` verifica 1–5.

## Domínios

### Execução

`/processar` → valida filtros (`regras.filtros_obrigatorios_sem_valor`) → `execucao.jobs` cria o
job → thread `execucao.runner` → `automacao.executar_relatorio(s)`. Estados por relatório:
`pendente`, `em_execucao`, `baixado`, `nao_baixado` (com `etapa`), `ignorado`. Uma execução por
sessão. A tela faz polling em `/execucoes/atual`.

### Login no Sienge

`automacao/login.py`: Sienge ID → e-mail → Microsoft (`loginfmt`) → senha → espera MFA → recusa
"continuar conectado" → sessão estável (4 confirmações no domínio Sienge, sem controles de login).
Falhou? Login interativo na mesma janela por até 180 s. Sessão é salva (DPAPI) mas **não
restaurada** (D6). Edge sem fallback para Chrome (D5).

### Catálogo e executores

Executor resolvido em `catalogo/regras.py`: ID do vínculo na operação → trecho da URL → ID do
relatório → nome. Sem executor = erro de configuração, nunca clique genérico. Particularidade de
tela vai no executor do relatório.

### Downloads

Arquivo novo (posterior à marca), sem temporário, tamanho estável por 3 ciclos; nome
`<relatório>_<empresa>_<data>` sem sobrescrever; cópia para `<destino>\Automação CAP` só em pasta
local/UNC. Sucesso só com arquivo confirmado no destino.

### Usuários e permissões

`IdAcesso`: 1 Administrador (tudo), 2 Cadastro de operação (Acompanhamento e Logs), 3 Execução.
Usuário recarregado do banco a cada requisição; inativo/excluído perde a sessão (D8). Senhas novas
em hash scrypt; senha legada em texto puro ainda é aceita no login (tabela compartilhada).

## Gates antes de fechar tarefa de código

1. `python -m compileall -q src tests run.py`
2. `pyright` com o `.venv` — 0 erros
3. `node --check` no JS estático (os scripts dos templates são checados pelos testes)
4. `python -m pytest`

Se um gate não puder rodar, diga o motivo, o comando e o risco. Mudança de frontend: renderizar as
páginas e conferir o HTML.

## Processo para feature nova

Spec em `docs/specs/<feature>.md` (problema, não objetivos, regras, bordas, riscos, plano de teste,
aceite) → aprovação explícita → design listando módulos → implementação em fatias → atualizar
`ARCHITECTURE.md`, `projectmap.md` e `DECISIONS.md` se mudar responsabilidade.

## Testes anti-atalho

- Permissão: perfil e usuário inativo, não visibilidade de botão.
- Automação: propagação de estado e etapa, não texto de log.
- Download: arquivo antigo, temporário e instável.
- Nada de rede, Sienge ou SQL Server: dublês em `tests/fakes.py` e `unittest.mock`.

## Convenções de commit

- Conventional Commits em português, sem acento no assunto: `feat(automacao): ...`,
  `fix(web): ...`, `refactor: ...`, `docs: ...`, `test(...)`, `chore(release): ...`.
- Versão e `CHANGELOG.md` são gerados pelo `python-semantic-release` no workflow — não edite à mão.
- **Nunca adicionar trailer de coautoria de IA** nos commits deste repositório.
- Branch de trabalho a partir de `main`; commit/push só quando o usuário pedir.

## Armadilhas conhecidas

- `.env` (raiz) e `.config/` têm credenciais reais do SQL Server. Nunca copie valores para arquivo
  versionado, log ou resposta.
- O `FLASK_SECRET_KEY` real esteve fixo no código e no manual da primeira versão (D1): deve ser trocado.
- `APP_HOST=0.0.0.0` expõe o app na rede; o checklist avisa.
- Logs no banco estão pausados (`APP_SAVE_LOGS=false`); diagnóstico pelo log técnico em
  `%LOCALAPPDATA%\AppCaptacao\logs\appcaptacao.log`.
- Os executores dependem de seletores do Sienge (MUI): mudança de layout quebra o relatório afetado.
- `extrato_saldo_devedor_presente.py` passa de 500 linhas (D10); os testes fazem patch das
  funções internas dele.
- Testes usam `pythonpath = ["src", "."]` (`pyproject.toml`); imports seguem `app_captacao.*`.

## Documentação de referência

- [README.md](README.md) — uso, instalação e atalho
- [docs/AI_CONTRACT.md](docs/AI_CONTRACT.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·
  [docs/projectmap.md](docs/projectmap.md) · [docs/DECISIONS.md](docs/DECISIONS.md)
- [docs/processos/](docs/processos/README.md) — execução, login, catálogo, downloads
- [docs/INSTALACAO_E_DISTRIBUICAO.md](docs/INSTALACAO_E_DISTRIBUICAO.md) · [docs/LOGS_E_ERROS.md](docs/LOGS_E_ERROS.md)
