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

1. trecho da URL (`RELATORIOS_EXECUTORES_URL`): o trecho precisa terminar a rota, então
   `/common/page/723` não casa com `/common/page/7230`;
2. ID do relatório (`RELATORIOS_EXECUTORES_RELATORIO`);
3. nome (`RELATORIOS_EXECUTORES`), comparado sem acento e sem diferença de maiúsculas. Nome com
   texto a mais ("Relatório de Preço Total de Vendas - EBM") usa a chave mais longa contida nele.

O ID do vínculo na operação (`IdCapRecursoRelatorioOperacao`) não decide o executor: é só a ordem
de criação da linha de vínculo.

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

## Campos do Sienge por executor

[catalogo/campos_sienge.py](../../src/app_captacao/catalogo/campos_sienge.py) declara, para cada
executor, os campos da tela do Sienge que ele preenche: rótulo, id/name, tipo, se a tela exige
(asterisco), o valor padrão da tela e quais identificadores e trechos de nome do cadastro o
executor aceita para cada campo. As telas foram lidas no Sienge em 2026-10-20
([auditoria](../auditoria-filtros-sienge.md)); a regra está em
[specs/filtros-validados-no-sienge.md](../specs/filtros-validados-no-sienge.md) e na D23.

- **Declaração = código.** `tests/catalogo/test_campos_sienge.py` lê cada executor e falha se ele
  procurar um filtro que não está declarado (ou o contrário), ou se a regra de busca for outra.
- **Filtro sem campo nunca passa calado.** Filtro do cadastro que nenhum campo do executor recebe
  (`regras.filtros_sem_campo_no_sienge`) aparece na mensagem do relatório ("Não aplicado(s) no
  Sienge, sem campo na tela: ...") e no log técnico. Com `APP_RECUSAR_FILTROS_SEM_CAMPO=true`, a
  tela principal e a automação recusam a execução (etapa `configuracao`). Ações de clique não são
  parâmetros e ficam de fora.
- **Obrigatoriedade vem do Sienge.** Filtro opcional no app só quando a tela não exige o campo (ou
  traz um padrão, como "Posição em", que vem com a data do dia) **e** o executor deixa o campo
  como está quando o filtro vem vazio (`aceita_vazio`). Hoje são opcionais: centro de custo de
  Títulos quitados/distratados, Reparcelamento e Contas a receber; empreendimento do Preço total de
  vendas; "Posição em" do Unidades e do Extrato cliente histórico; e os filtros de valor fixo.
- **Auditoria.** `tools/auditar_filtros_sienge.py --email <conta>` abre cada tela no Edge da
  automação (só leitura), cruza com as declarações e, com banco, com o cadastro, e regrava
  [docs/auditoria-filtros-sienge.md](../auditoria-filtros-sienge.md). Rode quando um relatório
  quebrar ou antes de ligar `APP_RECUSAR_FILTROS_SEM_CAMPO`.

No relatório **Unidades**, o filtro `filter.selecao` é fixo em "por Empreendimento" e preenchido
automaticamente. A regra vale para o executor `unidades` (não para quem tem "unidades" no nome) e
fica em `FILTROS_FIXOS_POR_EXECUTOR`, em `catalogo/regras.py`: a tela de execução, a de
Acompanhamento e o payload da operação usam a mesma tabela.

O filtro **"Posição em"** do Unidades vai para o campo `filter.dtHistorica` da tela (page/811). O
executor reconhece o filtro pelo campo identificador (`filter.dtHistorica`/`dtHistorica`) ou pelo
nome "Posição em", converte a data para `dd/mm/aaaa`, preenche a cada iteração e confere o valor
na tela antes do ENTER: se o Sienge não ficou com a data pedida, o relatório falha em vez de baixar
com a data errada. Sem valor, o Sienge usa a data do dia. O **Extrato cliente histórico** tem o
mesmo campo ("Posição em*", `name="dtHistorico"`) e o mesmo tratamento. No Unidades, o
**Empreendimento** é obrigatório: sem ele o Sienge recusa com "O campo 'Empreendimento' deve ser
preenchido.".

## Cadastro de operações (tela Acompanhamento)

- Perfis 1 (Administrador) e 2 (Cadastro de operação).
- Nome de operação ativa é único; a operação precisa de pelo menos um relatório.
- Ao vincular um relatório, os filtros dele são copiados para a operação com valor vazio; os
  valores são salvos depois, no modal de relatórios.
- Desvincular e inativar são lógicos (`IdAtivo = 0`).

## Como adicionar um relatório novo

1. Cadastrar o relatório e os filtros nas tabelas do catálogo.
2. Criar `automacao/relatorios/executores/<nome>.py` com `executar(...)`. Depois de exportar,
   esperar o arquivo (`renomear_download`) e só então `fechar_janelas_extras` (D22).
3. Registrar em `automacao/relatorios/registro.py` e mapear ID/URL/nome em `catalogo/regras.py`.
4. Declarar a tela em `catalogo/campos_sienge.py`: os campos que o executor preenche, lidos na
   tela do Sienge (obrigatório, padrão, `aceita_vazio` para o filtro que pode ficar vazio). O
   teste de consistência falha até a declaração bater com o código.
5. Rodar `tools/auditar_filtros_sienge.py` e conferir a tela nova em
   `docs/auditoria-filtros-sienge.md`.
6. Testar o roteamento (executor escolhido) e o preenchimento com dublês, sem rede.
