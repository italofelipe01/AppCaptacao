# Relatórios, filtros e operações

O comportamento da automação é parametrizado pelo banco. Relatório não é só uma URL: é uma
entidade com filtros, ações e um executor dedicado.

## Tabelas (SQL Server)

| Tabela (padrão) | Variável | Papel |
| --- | --- | --- |
| `dbo.CapRecursoRelatorio` | `RELATORIO_TABLE` | Catálogo: `IdCapRecursoRelatorio`, `NomeRelatorio`, `UrlRelatorio`, `IdAtivo` |
| `dbo.CapRecursoFiltro` | `FILTRO_CATALOGO_TABLE` | Filtros de cada relatório: nome, `TipoCampo`, `TipoCampoValor`, `IframeIndex`, `CampoIdentificador`, `Acao` |
| `dbo.CapRecursoOperacoes` | `OPERACAO_TABLE` | Operações (grupos de relatórios) |
| `dbo.CapRecursoRelatorio_X_Operacao` | `RELATORIO_X_OPERACAO_TABLE` | Relatórios de cada operação; a ordem de execução é a ordem do ID do vínculo |
| `dbo.CapRecursoFiltro_X_Operacao` | `FILTRO_X_OPERACAO_TABLE` | Valor de cada filtro dentro da operação (coluna `Valor`, `ValorPadrao` ou `ValorFiltro`) |
| `dbo.CapRecursoUsuario` | `USUARIO_TABLE` | Usuários do app e perfil (`IdAcesso`) |
| `dbo.CapRecursoLogConfiguracao` / `dbo.CapRecursoLogOperacao` | `LOG_CONFIG_TABLE` / `LOG_OPERACAO_TABLE` | Logs, gravados só com `APP_SAVE_LOGS=true` |

Colunas de auditoria (`IdLoginCriacao`, `IdLoginAlteracao`, `DataAlteracao`) e algumas chaves
de vínculo são opcionais: o código detecta se existem antes de usar.

## Contrato do filtro

| Campo | Uso |
| --- | --- |
| `TipoCampo` | Como localizar o campo: `ID`, `NAME`, `XPATH`, `CSS`... |
| `CampoIdentificador` | Identificador técnico no Sienge (ex.: `filter.empresa.cdEmpresaView`) |
| `IframeIndex` | Iframe onde o campo vive |
| `TipoCampoValor` | `DATE` converte para `dd/mm/aaaa`; `CLICK` é ação sem valor |
| `Acao` | Vazia ou `fill`/`fill_tab`/`type`/`write`/`preencher`/`send_keys` exigem valor; `click`, `enter`, `submit`, `wait` não |

Na tela, o valor chega como `filtro_<IdFiltro>` (ou pelo nome do filtro). Filtro com vários
valores separados por vírgula (ex.: várias empresas) é tratado pelo executor.

## Escolha do executor dedicado

Ordem de resolução em [catalogo/regras.py](../../src/app_captacao/catalogo/regras.py):

1. ID do vínculo na operação (`RELATORIOS_EXECUTORES_OPERACAO`);
2. trecho da URL (`RELATORIOS_EXECUTORES_URL`);
3. ID do relatório (`RELATORIOS_EXECUTORES_RELATORIO`);
4. nome normalizado (`RELATORIOS_EXECUTORES`).

| Executor | ID do relatório | Trecho da URL |
| --- | --- | --- |
| `extrato_cliente_historico` | 7 | `/common/page/3012` |
| `extrato_saldo_devedor_presente` | 2 | `/financeiro/contas-receber/relatorios/saldo-devedor` |
| `extrato_conciliado` | 6 | `/common/page/1424` |
| `contas_recebidas` | 8 | `/common/page/4929` |
| `contas_a_receber` | — | só pelo nome |
| `analise_resultado_sintetico` | 10 | `/common/page/354` |
| `analitico_propriedade` | — | só pelo nome (inclui "analítico de apropriações") |
| `posicao_saldos` | 11 | `/common/page/1320` |
| `retencao` | — | `/common/page/1669` |
| `titulos_quitados` | 12 | `/common/page/4145` |
| `titulos_distratados` | — | `/common/page/4140` |
| `preco_total_vendas` | 14 | `/common/page/723` |
| `relatorio_reparcelamento` | — | `/common/page/2458` |
| `mapa_venda` | — | `/common/page/5084` |
| `quadro_espelho` | — | `/comercial/gestao-de-unidades/quadro-espelho` |
| `unidades` | — | só pelo nome |
| `vendas` | 3 | `/common/page/708` |

Cada executor é um módulo em
[automacao/relatorios/executores/](../../src/app_captacao/automacao/relatorios/executores/)
com `executar(driver, wait, relatorio_config, contexto)`. O `contexto` entrega o logger e as
funções de campo e download da automação.

## Filtros opcionais por executor

| Executor | Campo opcional |
| --- | --- |
| `titulos_quitados`, `titulos_distratados`, `relatorio_reparcelamento`, `contas_a_receber` | Empreendimento/centro de custo (`centrocusto.cdempreendview`, `entity.empreend.cdempreendview`, `cdempreendview`) |
| `preco_total_vendas`, `unidades` | Empreendimento (`filter.empreend.cdempreendview`, `cdempreendview`) |

No relatório **Unidades**, o filtro `filter.selecao` é fixo em "por Empreendimento" e preenchido
automaticamente.

## Cadastro de operações (tela Acompanhamento)

- Perfis 1 (Administrador) e 2 (Cadastro de operação).
- Nome de operação ativa é único; a operação precisa de pelo menos um relatório.
- Ao vincular um relatório, os filtros dele são copiados para a operação com valor vazio; os
  valores são salvos depois, no modal de relatórios.
- Desvincular e inativar são lógicos (`IdAtivo = 0`).

## Como adicionar um relatório novo

1. Cadastrar o relatório e os filtros nas tabelas do catálogo.
2. Criar `automacao/relatorios/executores/<nome>.py` com `executar(...)`.
3. Registrar em `automacao/relatorios/registro.py` e mapear ID/URL/nome em `catalogo/regras.py`.
4. Se algum filtro for opcional, incluir em `eh_filtro_opcional_relatorio`.
5. Testar o roteamento (executor escolhido) e o preenchimento com dublês, sem rede.
