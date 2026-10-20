# Aba de parâmetros no consolidado

Aprovada em 2026-10-20, junto com
[filtros-validados-no-sienge.md](filtros-validados-no-sienge.md), da qual depende para que nenhum
filtro do cadastro seja ignorado. Resultado no fim.

## Problema

O consolidado (`<Relatório>_consolidado_<data>.xlsx`) traz os dados, a origem e a conferência, mas
não diz com quais filtros a extração foi feita. Quem recebe o arquivo não tem acesso ao app e não
consegue saber, por exemplo, qual "Posição em", grupo de empresa ou seleção foi usado. A aba
**Dados** só tem os campos que o Sienge imprime no cabeçalho de cada arquivo, e isso varia por
relatório: o Unidades imprime Empresa, Empreendimento e Posição em, mas não Grupo de empresa nem
Seleção. Os valores da operação também podem mudar depois da extração, então consultar a operação
mais tarde não reconstrói o que foi usado.

## Não objetivos

- Arquivo de parâmetros para relatórios sem consolidado (10 dos 17 executores): continuam como hoje.
- Mudar telas, cadastro de filtros ou operações (o frontend não muda).
- Comparar os filtros com o que o Sienge imprimiu no cabeçalho de cada arquivo.
- Mostrar e-mail ou qualquer credencial do Sienge.

## Regras de comportamento

1. Todo consolidado gerado ganha a aba **Parâmetros**, logo depois de **Dados** (Dados,
   Parâmetros, Origem, Conferência).
2. A aba é só a tabela **Filtro | Campo no Sienge | Valor usado | Observação**, com uma linha por
   filtro do relatório, na ordem do cadastro. Não traz quem executou, quando nem a operação.
3. **Campo no Sienge** é o rótulo do campo na tela do relatório (por exemplo, "Posição em"),
   tirado da declaração validada do executor. É onde o valor foi aplicado e como o receptor o
   encontra no Sienge.
4. Os valores são os que a automação recebeu e aplicou nesta execução, não os do banco no momento
   da consolidação.
5. Formatação dos valores:
   - Data (`TipoCampoValor` DATE): `dd/mm/aaaa`.
   - Lista (`242,101`): `242, 101`.
   - Filtro de valor fixo do executor (como "Seleção" do Unidades): o valor, com a observação
     "Preenchido automaticamente".
   - Filtro vazio: valor `—`, com a observação "Não informado: o Sienge usa o padrão da tela".
   - Ação sem valor (`CLICK`): valor `—`, com a observação "Ação automática".
6. A aba não participa da conferência. Se a conferência falha, nada é gravado, como hoje.

## Casos de borda

- Relatório sem filtros cadastrados, ou payload não encontrado no fim da execução: a aba sai com
  a linha "Nenhum filtro cadastrado para este relatório".
- Data em formato não reconhecido: mostrada como veio.
- Execução que parou no meio: o relatório não é consolidado (regra atual), então não há aba.

## Riscos

- Filtro cadastrado com nome pouco claro: aparece como está no cadastro, mas a coluna Campo no
  Sienge mostra o rótulo real da tela.
- A garantia de que o valor foi aplicado vem de
  [filtros-validados-no-sienge.md](filtros-validados-no-sienge.md): declaração validada na tela,
  recusa de filtro sem declaração e conferência do valor antes de gerar o relatório. Sem ela, a
  aba poderia mostrar um valor que o Sienge não recebeu.

## Design

- `consolidacao/parametros.py` (novo): monta as linhas da aba a partir dos filtros do payload
  (lista de dicionários, já com o rótulo do campo no Sienge). Só importa de `core/` (fronteira 9).
- `consolidacao/consolidador.py`: `consolidar(...)` recebe os filtros opcionais e `_gravar`
  escreve a aba depois de Dados.
- `execucao/runner.py`: passa os filtros de cada relatório, com o rótulo do campo no Sienge vindo
  de `catalogo/campos_sienge.py`, para `consolidar`.
- Documentação: `processos/consolidacao_de_relatorios.md`, `ARCHITECTURE.md` e `projectmap.md`
  (módulo novo).

## Plano de teste

- Consolidação: a aba existe, vem depois de Dados e lista os filtros na ordem, cada um com o
  rótulo do campo no Sienge; data em
  `dd/mm/aaaa`; lista com espaço; filtro fixo, vazio e `CLICK` com a observação certa; relatório
  sem filtros; conferência que falha não grava nada.
- Runner: os filtros da execução chegam a `consolidar`, tanto em operação quanto em execução
  avulsa.
- Manual: uma operação real do Unidades, abrindo o consolidado e conferindo a aba contra a
  operação cadastrada.

## Critérios de aceite

- Os quatro gates do CLAUDE.md passam.
- No consolidado real do Unidades, a aba Parâmetros mostra a Posição em, o Grupo de empresa, a
  Empresa, o Empreendimento e a Seleção usados, cada um com o campo correspondente no Sienge.

## Resultado (2026-10-20)

Implementado conforme [D24](../DECISIONS.md). Diferença do desenho: as linhas são montadas em
`catalogo/parametros.py`, não em `consolidacao/parametros.py`. O rótulo do campo no Sienge vem da
declaração do catálogo, e a consolidação só pode importar de `core/`; por isso ela recebe as
linhas prontas, em texto, do `execucao/runner.py`. Enquanto a recusa de filtro sem campo estiver
desligada, um filtro não aplicado aparece na aba com "NÃO APLICADO: sem campo correspondente na
tela do Sienge". A aba foi testada com planilhas geradas nos testes. A execução ao vivo de um
consolidado completo ficou para quando o login do Sienge voltar a responder.
