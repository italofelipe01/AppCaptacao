# Project Map

Onde implementar cada tipo de mudança. Para o porquê das fronteiras, ver
[ARCHITECTURE.md](ARCHITECTURE.md).

## Estrutura

```text
AppCaptacao/
├── Iniciar AppCaptacao.bat     duplo clique: .venv + checklist + app
├── run.py                      entrada em desenvolvimento (checklist, depois o app)
├── src/app_captacao/
│   ├── app.py                  instância Flask, usuário da sessão, registro das rotas
│   ├── core/
│   │   ├── config/             environment.py (.env, caminhos), dpapi.py, settings.py
│   │   ├── database/           connection.py (pyodbc + pymssql), sql.py (execute, fetch, introspecção)
│   │   ├── security/           auth.py, perfis.py, sessao_usuario.py, network_auth.py (não ligado)
│   │   ├── persistence/        usuarios.py, logs.py
│   │   └── shared/             texto.py, arquivos.py (nome/pasta), navegador_local.py, log_tecnico.py
│   ├── catalogo/               relatorios.py, regras.py, operacoes.py, operacao_relatorios.py
│   ├── automacao/              config, navegador, login, sessao, campos, downloads, erros, execucao
│   │   └── relatorios/         registro.py + executores/<relatorio>.py (17 executores)
│   ├── consolidacao/           layouts.py (7 relatórios), leitura.py, consolidador.py (conferência + planilha)
│   ├── execucao/               jobs.py (estado), runner.py (thread + consolidação no fim)
│   ├── inicializacao/          dependencias.py, verificacoes.py (checklist do run.py)
│   ├── web/                    routes_auth, routes_execucao, routes_usuarios,
│   │                           routes_acompanhamento, routes_logs, registro, erros, auditoria
│   └── desktop/                desktop_app.py (janela do .exe), config_installer.py
├── project/                    FRONTEND: templates/ e static/ (não alterar sem pedido)
├── tests/                      espelha src/: core, catalogo, web, automacao, execucao, ...
├── packaging/                  .spec do PyInstaller e ícone
├── scripts/                    gerar_executaveis.ps1, criar_atalho.bat/.ps1
├── tools/baixa_pdfs/           ferramenta independente (não faz parte do app)
└── docs/                       contrato, arquitetura, processos, decisões, specs
```

## Onde mudar

| Quero... | Arquivo(s) |
| --- | --- |
| Nova variável de ambiente | `core/config/settings.py` (app) ou `automacao/config.py` (Selenium) + `.env.example` |
| Nova tela ou rota | `web/routes_<tela>.py` + registrar em `app.py`; template em `project/templates/` |
| Mudar permissão | decorator `access_required(...)` na rota; perfis em `core/security/perfis.py` |
| SQL de usuário | `core/persistence/usuarios.py` |
| SQL de catálogo/operação | `catalogo/relatorios.py`, `catalogo/operacoes.py`, `catalogo/operacao_relatorios.py` |
| Qual executor atende um relatório | `catalogo/regras.py` |
| Filtro opcional/obrigatório | `catalogo/regras.py` (`eh_filtro_opcional_relatorio`, `acao_exige_valor`) |
| Novo relatório do Sienge | `automacao/relatorios/executores/<nome>.py` + `registro.py` + `regras.py` ([guia](processos/relatorios_e_filtros.md#como-adicionar-um-relatório-novo)) |
| Seletores do login Sienge/Microsoft | `automacao/login.py` |
| Abertura do Edge/Chrome | `automacao/navegador.py` |
| Detecção, nome ou cópia de download | `automacao/downloads.py` (regras de nome em `core/shared/arquivos.py`) |
| Consolidar um relatório novo ou ajustar a conferência | `consolidacao/layouts.py` + planilha sintética em `tests/consolidacao/planilhas_sienge.py` ([guia](processos/consolidacao_de_relatorios.md#como-adicionar-um-relatório)) |
| Preenchimento de campo comum (autocomplete, iframe) | `automacao/campos.py` |
| Estados e resumo da execução | `automacao/execucao.py` e `execucao/runner.py` |
| Checklist de inicialização | `inicializacao/verificacoes.py` |
| Configurador do executável | `desktop/config_installer.py` |
| Build dos executáveis | `packaging/*.spec`, `scripts/gerar_executaveis.ps1` |

## Testes

| Pasta | Cobre |
| --- | --- |
| `tests/core/` | configuração, conexão, senha, sessão/usuário, log técnico |
| `tests/catalogo/` | escolha do executor, filtros obrigatórios e fixos, consulta do catálogo |
| `tests/web/` | rotas (usuários, acompanhamento, erros) e scripts dos templates |
| `tests/automacao/` | execução em sequência, login, downloads, executor do saldo devedor |
| `tests/execucao/` | job em segundo plano, limite de memória e consolidação no fim |
| `tests/consolidacao/` | leitura do layout do Sienge, conferência e planilha gerada (planilhas sintéticas) |
| `tests/inicializacao/` | checklist e leitura do requirements |
| `tests/desktop/` | janela desktop (com customtkinter simulado) |
| `tests/test_fronteiras.py` | fronteiras entre camadas |

Dublês de banco em `tests/fakes.py`. Nenhum teste acessa rede, Sienge ou SQL Server.

## Limite de tamanho

Arquivos `.py` novos ficam abaixo de 500 linhas. Exceção conhecida:
`automacao/relatorios/executores/extrato_saldo_devedor_presente.py` (~1440 linhas), mantido
inteiro porque os testes e o fluxo dependem das funções internas (ver D10 em
[DECISIONS.md](DECISIONS.md)).
