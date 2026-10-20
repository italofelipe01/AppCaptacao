# Filtros do app validados no Sienge

Aprovada em 2026-10-20 ("implemente momentaneamente mesmo sem acesso ao SQL [...] na medida do
possível. Não quebre funções"). Pré-requisito de
[parametros-no-consolidado.md](parametros-no-consolidado.md). Resultado no fim.

## Problema

Os 17 executores procuram no payload uma lista fixa de filtros pelo campo identificador e
ignoram o resto, sem aviso. Um filtro cadastrado no app que o executor não conhece é descartado, e
o Sienge gera o relatório com o padrão da tela. Caso real: o "Posição em" do Unidades, corrigido
em 2026-10-20. Os arquivos de 16/10 saíram com a data do dia, não com a data cadastrada.

O inverso também existe. O executor do Unidades procura `filter.dtInicioStr` e `filter.dtFimStr`,
que não existem na tela do relatório (page/811). Se alguém cadastrar esses filtros, o relatório
trava esperando um campo que não existe.

Hoje, para saber quais filtros do cadastro são realmente aplicados, e se a obrigatoriedade do app
bate com a do Sienge, é preciso ler o código e abrir o Sienge, relatório por relatório.

## Não objetivos

- Mudar o frontend ou o formato do cadastro (tabelas `CapRecurso*`).
- Preencher filtros que não estão no cadastro. Campos do Sienge sem filtro no app continuam com o
  padrão da tela, e a auditoria registra isso.
- Validar o valor contra os dados do Sienge (por exemplo, se a empresa existe).

## Regras de comportamento

1. **Declaração por executor.** Cada executor declara os campos do Sienge que aplica: rótulo na
   tela, id do campo, tipo (texto, data, lookup, select, checkbox), se é obrigatório no Sienge e se
   a tela traz valor padrão. As declarações ficam em `catalogo/campos_sienge.py` e são a fonte
   única: o executor localiza os filtros por elas, e a validação usa a mesma tabela.
2. **Casamento.** Um filtro do cadastro casa com uma declaração pelo campo identificador ou pelo
   nome, sem acento. Quando os dois casam com declarações diferentes, vale o campo.
3. **Nenhum filtro ignorado.** Filtro do cadastro sem declaração no executor do relatório é erro de
   configuração:
   - a tela principal e a execução de operação recusam antes de começar, listando os filtros;
   - se o relatório chegar à automação mesmo assim, ele termina `nao_baixado`, com etapa
     `configuracao`, sem abrir o Sienge.
4. **Obrigatoriedade vem do Sienge.**
   - Campo obrigatório no Sienge e sem valor padrão na tela: o filtro é obrigatório no app.
   - Campo obrigatório com padrão na tela (como "Posição em", que vem com a data do dia), ou
     campo opcional: o filtro é opcional no app.
   - Esta regra substitui a lista manual de `regras.eh_filtro_opcional_relatorio`.
5. **Conferência na tela.** Cada campo preenchido é conferido na tela antes de gerar o relatório,
   como já é feito com o "Posição em". Se o Sienge não ficou com o valor, o relatório falha em vez
   de sair com outro filtro.
6. **Auditoria.** `tools/auditar_filtros_sienge.py` abre cada relatório ativo do catálogo no Edge
   da automação, já logado, lê os campos do formulário e cruza com o cadastro e as declarações.
   Ela aponta quatro divergências:
   - (a) filtro do app sem campo correspondente no Sienge;
   - (b) declaração cujo campo não existe na tela;
   - (c) campo obrigatório no Sienge, sem padrão, que não tem filtro nem valor fixo no app;
   - (d) obrigatoriedade do app diferente da do Sienge.

   A auditoria só lê: não gera relatório e não altera o cadastro.

## Casos de borda

- Telas novas do Sienge (MUI: Saldo devedor, Quadro espelho) não marcam `obrigatorio="true"`: a
  auditoria usa o asterisco do rótulo, e a declaração registra o que foi visto na tela.
- Campo que só aparece depois de um select (no Unidades, "Seleção: por Empreendimento" abre
  Empresa e Empreendimento): a auditoria aplica os valores fixos do executor antes de ler a tela.
- Filtro inativo no cadastro não entra no payload e não é cobrado.
- Filtro de valor fixo do executor (`FILTROS_FIXOS_POR_EXECUTOR`) também precisa de declaração.

## Riscos

- Ao ligar a regra 3, uma operação que hoje tem filtro ignorado deixa de executar até o executor
  ser corrigido ou o filtro ser inativado. Por isso a ordem das fatias: auditoria, correção dos
  executores e só então a recusa.
- A busca de filtros muda nos 17 executores. Cada um ganha teste de preenchimento com dublês.
- A auditoria reflete o layout do Sienge no dia em que roda; deve ser repetida quando um relatório
  quebrar.

## Plano em fatias

1. **Auditoria.** Ferramenta e uma rodada em todos os relatórios ativos. O resultado vai para
   `docs/auditoria-filtros-sienge.md`: relatório, filtro do app, campo no Sienge, obrigatório,
   padrão da tela e situação.
2. **Declarações e correções.** Declarações dos 17 executores e correção dos que divergirem, um
   relatório por vez, com testes.
3. **Recusa.** Regras 3 e 4 na validação das rotas e na automação.
4. **Aba Parâmetros** no consolidado ([parametros-no-consolidado.md](parametros-no-consolidado.md)).

## Plano de teste

- Validação: filtro sem declaração faz `/processar` recusar e listar o filtro; filtro com
  declaração passa; obrigatoriedade derivada da declaração.
- Automação: filtro sem declaração termina `nao_baixado`, etapa `configuracao`, sem abrir o
  relatório; valor que não fica na tela falha antes do ENTER.
- Por executor: cada campo declarado é preenchido quando tem valor, e conferido.
- Fronteiras: `catalogo/campos_sienge.py` não importa de `automacao/`.
- Manual: auditoria sem divergências nos relatórios ativos e uma operação real executada.

## Critérios de aceite

- Os quatro gates do CLAUDE.md passam.
- A auditoria não aponta divergências (a) a (d) nos relatórios ativos do catálogo.
- Nenhum filtro do cadastro é descartado sem aviso.

## Dependência

A auditoria precisa ler o cadastro (`CapRecursoRelatorio` e `CapRecursoFiltro`). Em 2026-10-20 o
login do SQL Server configurado no `.env` foi recusado (erro 18456).

## Resultado (2026-10-20)

Implementado conforme [D23](../DECISIONS.md), sem acesso ao banco. Telas lidas ao vivo no Sienge;
resultado em [auditoria-filtros-sienge.md](../auditoria-filtros-sienge.md).

- **Declarações:** `catalogo/campos_sienge.py`, para os 17 executores. Diferença do desenho: os
  executores **não** passaram a ler a declaração. Cada um mantém a própria busca (são cinco
  variações, com regras exata e por sufixo e com trecho de nome), e
  `tests/catalogo/test_campos_sienge.py` trava declaração e código juntos. Reescrever a busca dos
  17 arriscaria o que funciona.
- **Regra 3 (nenhum filtro ignorado):** `regras.filtros_sem_campo_no_sienge`. Diferença do
  desenho: a recusa existe, mas fica desligada (`APP_RECUSAR_FILTROS_SEM_CAMPO=false`), porque sem
  o cadastro não dá para saber se alguma operação ativa tem filtro hoje ignorado. Enquanto isso o
  filtro aparece na mensagem do relatório, no log técnico e na aba Parâmetros.
- **Regra 4 (obrigatoriedade):** opcional só quando a tela não exige (ou traz padrão) **e** o
  executor aceita vazio. Vários executores digitam o valor vazio por cima do padrão do Sienge;
  afrouxar só pela tela quebraria esses relatórios. O Empreendimento do Unidades passou a ser
  obrigatório (o Sienge recusa sem ele, testado ao vivo).
- **Regra 5 (conferência na tela):** feita nos campos corrigidos ("Posição em" do Unidades e do
  Extrato cliente histórico). Os demais campos seguem como estavam.
- **Correções nos executores:** Unidades (sem `dtInicioStr`/`dtFimStr`/`tpRelatorio`, que não
  existem na tela), Extrato cliente histórico ("Posição em"), Analítico de apropriações ("Correção
  até") e Quadro espelho (sem datas, que não existem na tela).
- **Pendente:** ler o cadastro (divergência (a)) com o banco no ar; conferir a tela do Contas a
  receber (URL desconhecida); depois disso, ligar `APP_RECUSAR_FILTROS_SEM_CAMPO`.
