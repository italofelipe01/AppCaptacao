# AI Contract

Regras obrigatórias para qualquer agente de IA ou pessoa que altere este repositório. Têm
prioridade sobre atalhos locais e correções pontuais que piorem a arquitetura. Incorpora as regras
do antigo "Roteiro para IA" (`docs/originais/roteiro_ia_superprompt.docx`).

## Regras não negociáveis

- Não mudar a estrutura, as funções e as features do frontend (`project/templates`,
  `project/static`) sem pedido explícito. Nomes de endpoint e URLs usados pelos templates são contrato.
- Não colocar regra de negócio em template Jinja, JavaScript ou CSS. A tela recebe estado pronto.
- Não escrever SQL fora de `core/persistence/`, `catalogo/` e `core/database/`.
- Não gravar senha, token ou credencial real em arquivo versionado. `.env`, `.config/` e `*.env.enc`
  nunca entram no git.
- Não criar exceção por usuário, empresa, CNPJ ou nome de relatório fora das tabelas de roteamento
  de `catalogo/regras.py`.
- Não exibir erro técnico como sucesso, nem detalhe técnico (SQL, driver) na tela.
- Não deixar execução sem estado: todo relatório termina `baixado`, `nao_baixado` ou `ignorado`.
- Não encerrar tarefa de código sem rodar os gates (ver abaixo) ou registrar por que não rodaram.

## Regras de domínio (automação do Sienge)

- O app é uma plataforma parametrizada por banco, não um robô de cliques fixos: consulte o cadastro
  antes de assumir que um filtro ou relatório é fixo.
- Nunca presuma que relatórios compartilham o mesmo fluxo de tela. Particularidade vai para o
  executor dedicado do relatório.
- Relatório sem executor é lacuna de configuração: falhe com mensagem clara, não improvise cliques.
- Prefira identificador estável (`id`, `name`, cadastro) a XPath frágil ou coordenadas.
- Login só conta como concluído com sessão estável no domínio Sienge e sem tela de login ativa.
- Edge é o navegador padrão; Chrome só por configuração. Não há troca automática.
- Destino "SharePoint" é pasta sincronizada ou caminho UNC; não há upload por URL.
- Sucesso de download exige arquivo estável, renomeado e confirmado no destino.
- Mudança de layout do Sienge pede ajuste localizado no executor ou em `automacao/login.py`.

## Onde cada lógica mora

| Lógica | Lugar |
| --- | --- |
| Rotas e validação da requisição | `src/app_captacao/web/routes_*.py` |
| Login, perfis, sessão do app | `src/app_captacao/core/security/` |
| SQL de usuários e logs | `src/app_captacao/core/persistence/` |
| Catálogo, operações, roteamento de executor | `src/app_captacao/catalogo/` |
| Selenium: navegador, login Sienge, downloads | `src/app_captacao/automacao/` |
| Particularidade de um relatório | `src/app_captacao/automacao/relatorios/executores/<relatorio>.py` |
| Estado dos jobs e thread de execução | `src/app_captacao/execucao/` |
| Variáveis de ambiente | `core/config/settings.py` (app) e `automacao/config.py` (Selenium) |

## Processo para mudança relevante

1. Entender o domínio em [projectmap.md](projectmap.md) e no módulo afetado.
2. Feature nova ou mudança central: spec em `docs/specs/<feature>.md` antes do código (ver
   [specs/README.md](specs/README.md)) e aprovação explícita.
3. Implementar em fatias: domínio → serviço → rota/UI → testes.
4. Mudou responsabilidade entre módulos: atualizar [ARCHITECTURE.md](ARCHITECTURE.md),
   [projectmap.md](projectmap.md) e [DECISIONS.md](DECISIONS.md).

## Gates

```powershell
.\.venv\Scripts\python.exe -m compileall -q src tests run.py
npx pyright@1.1.414 --pythonpath .venv\Scripts\python.exe
node --check project\static\js\menu.js
.\.venv\Scripts\python.exe -m pytest
```

Os scripts embutidos nos templates são validados com `node --check` pelo
`tests/web/test_templates_js.py`.

## Testes anti-atalho

Toda regra nova precisa de teste que falhe contra o atalho correspondente:

- Permissão: testar perfil e usuário inativo, não visibilidade de botão.
- Automação: testar propagação de estado e etapa, não texto de log.
- Download: testar arquivo pré-existente, temporário e instável, não só o caminho feliz.
- Testes não acessam rede, Sienge nem SQL Server: usar dublês (`tests/fakes.py`).
