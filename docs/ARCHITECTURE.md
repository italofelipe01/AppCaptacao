# Arquitetura

## Visão de camadas

```text
Navegador do usuário (project/templates + project/static)
        │ HTTP local (127.0.0.1:4732)
        ▼
web/            rotas Flask: validam a requisição e orquestram
        │
        ├── core/security    login do app, perfis, usuário da sessão
        ├── core/persistence usuários e logs (SQL)
        ├── catalogo/        relatórios, filtros, operações, roteamento de executor (SQL + regras)
        └── execucao/        job em memória + thread de execução
                 │
                 ▼
          automacao/          Selenium: navegador → login Sienge → executor dedicado → download
                 │
                 ▼
          Sienge (web)  +  pasta de downloads  +  destino (pasta sincronizada/UNC)

core/config     .env, DPAPI, settings  ←  lido por todos
core/database   conexão SQL Server (pyodbc, fallback pymssql)
```

## Fronteiras (verificáveis por grep)

1. `core/` não importa de `catalogo/`, `automacao/`, `execucao/` nem `web/`.
2. `catalogo/` não importa de `automacao/`, `execucao/` nem `web/`.
3. `automacao/` não importa de `execucao/` nem `web/`; executores recebem o que precisam pelo `contexto`.
4. Rotas não escrevem SQL; persistência não lê `flask.g` (o usuário chega como parâmetro).
5. Toda leitura de variável de ambiente passa por `core/config/settings.py` ou
   `automacao/config.py`, que carregam o `.env` antes.
6. Endpoints mantêm o nome da função (sem Blueprint): `url_for` e `request.endpoint` nos
   templates dependem disso ([web/registro.py](../src/app_captacao/web/registro.py)).

## Fluxo de uma requisição

1. `before_request` ignora arquivos estáticos e carrega o usuário da sessão no banco
   ([sessao_usuario.py](../src/app_captacao/core/security/sessao_usuario.py)). Usuário inativo ou
   excluído perde a sessão; banco fora do ar mantém quem já estava autenticado.
2. Decorators `login_required` e `access_required(*perfis)` protegem a rota.
3. A rota valida a forma da requisição e chama `catalogo/` ou `core/persistence/`.
4. `ValueError` vira mensagem para o usuário; outras exceções vão para o log técnico com
   mensagem genérica ([web/erros.py](../src/app_captacao/web/erros.py)).

## Fluxo de uma execução

Ver [processos/execucao_de_relatorios.md](processos/execucao_de_relatorios.md). Resumo:
`/processar` → `execucao.jobs.create_execution_job` → thread `execucao.runner.run_execution_job`
→ `automacao.executar_relatorio(s)` → resultado no job (e no log do banco, se ativo).

## Perfis de acesso (`IdAcesso`)

| Perfil | Telas |
| --- | --- |
| 1 Administrador | Tudo: execução, Acompanhamento, Usuários, Logs (inclusive aba administrativa), Perfil |
| 2 Usuário com cadastro de operação | Execução, Acompanhamento, Logs de operação, Perfil |
| 3 Usuário de execução | Execução e Perfil |

O perfil vem do banco a cada requisição; o template só esconde botões, a permissão real é do backend.

## Estado e persistência

| Dado | Onde vive | Duração |
| --- | --- | --- |
| Usuários, catálogo, operações | SQL Server | Permanente |
| Logs de configuração/operação | SQL Server (se `APP_SAVE_LOGS=true`) | Permanente |
| Jobs de execução | Memória do processo (últimos 200 concluídos) | Até reiniciar o app |
| E-mail e destino da última execução | Memória, por sessão | Até sair ou reiniciar |
| Senha do Sienge | Só na thread da execução | Nunca gravada |
| Log técnico | `%LOCALAPPDATA%\AppCaptacao\logs` | Rotativo, 25 MB |

## Executáveis

`packaging/AppCaptacao.spec` empacota `desktop/desktop_app.py` (janela CustomTkinter que sobe o
servidor) com `project/` como dados. `packaging/ConfigurarAppCaptacao.spec` empacota o
configurador seguro. Ver [INSTALACAO_E_DISTRIBUICAO.md](INSTALACAO_E_DISTRIBUICAO.md).
