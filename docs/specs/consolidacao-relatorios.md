# Consolidação dos relatórios baixados

Aprovada em 2026-10-16 ("implemente", após a análise dos arquivos de uma operação real).

## Problema

Uma operação gera um arquivo por empresa/empreendimento para cada relatório, todos na mesma pasta.
Numa operação real com 7 relatórios e 3 empresas (a 242 com 3 empreendimentos) saíram 58 arquivos
misturados, e cada um aparecia duas vezes: a pasta de downloads e o destino eram a mesma pasta, e
a cópia caía ao lado do original com `_2`. Para analisar, alguém precisa abrir arquivo por arquivo,
tirar o cabeçalho e os totais do layout de impressão do Sienge e colar tudo numa planilha. O nome
do arquivo nem diz o empreendimento (`_242_`, `_242_..._3`, `_242_..._4`): só o conteúdo diz.

## Não objetivos

- Consolidar relatórios cujo layout não foi visto num arquivo real (10 dos 17 executores): eles
  continuam sendo entregues como hoje, sem consolidado.
- Juntar arquivos de execuções diferentes ou arquivos antigos que já estejam na pasta.
- Reprocessar uma pasta manualmente pela tela (o frontend não muda).
- Mudar o nome dos arquivos baixados.

## Regras de comportamento

1. Cada arquivo final vai para uma pasta com o nome do relatório: `<base>\<Relatório>\`, onde
   `<base>` é `<destino>\Automação CAP` (com destino informado) ou a pasta de downloads (sem destino).
2. Quando a `<base>` é a própria pasta de downloads, o arquivo é **movido** para a pasta do
   relatório, não copiado: nenhum arquivo aparece duas vezes. Com destino em outro lugar, continua
   sendo copiado, e a cópia é conferida pelo tamanho.
3. No fim da execução, cada relatório `baixado` cujo executor tem layout conhecido ganha um
   consolidado `<Relatório>_consolidado_<AAAA-MM-DD>.xlsx` na mesma pasta, só com os arquivos
   daquela execução. Nada é sobrescrito (`_2`, `_3`...).
4. O consolidado tem as abas **Dados** (uma tabela plana: arquivo de origem, campos do bloco de
   filtros do Sienge como colunas, colunas do relatório), **Origem** (arquivo, empresa,
   empreendimento/centro de custo, linhas) e **Conferência** (cada total conferido).
5. Linhas de título, filtros, subtotais, totais, notas de rodapé e a linha "SIENGE / STARIAN" não
   entram em Dados. Datas `dd/mm/aaaa` viram data do Excel.
6. Cada arquivo é conferido contra os totais que o próprio Sienge imprime nele. A diferença
   aceita é o arredondamento: até R$ 0,005 por linha somada (mínimo R$ 0,01); contagens precisam
   bater exatamente. Se qualquer conferência falhar, o consolidado **não** é gerado e o motivo
   aparece no relatório; os arquivos originais ficam intactos.
7. A consolidação nunca muda o estado do relatório: ele continua `baixado`. O resultado aparece
   na mensagem do relatório ("Consolidado: ..." ou "Consolidado não gerado: ...") e o
   consolidado vira o "Arquivo final" mostrado na tela.
8. `APP_CONSOLIDAR_RELATORIOS=false` desliga a consolidação (regras 1 e 2 continuam valendo).

### Particularidades por relatório

| Executor | Tabela começa em | Campos do bloco de filtros | Conferência |
| --- | --- | --- | --- |
| `analitico_propriedade` | `Data` | Centro de custo, Período, Conta | Valor das entradas e das saídas |
| `extrato_cliente_historico` | `Par` | Empresa, Empreendimento, Cliente(s), Título, Data de emissão, Correção até, Corretor, Área privativa, Documento, Unidades | Saldo atual, Valor baixa, Acréscimo, Desconto, Recto líquido (soma dos "Total título") |
| `mapa_venda` | `Contrato` | Empresa, Empreendimento, Período | O Sienge não imprime total |
| `preco_total_vendas` | `Contrato` | Empresa, Empreendimento, Período | Vl. contrato, Preço total venda |
| `titulos_distratados` | `Data` | Empresa, Período de distrato, Área de negócio, Centro de custo | 4 colunas de valor ("Total da empresa") |
| `vendas` | `N. do contrato` | Empresa, Empreendimento, Período do contrato | VGV = Contratos + Propostas do "Total Geral" |
| `unidades` | `Unidade` | Empresa, Empreendimento, Posição em | Quantidade de unidades do "Total Geral" |

- **Analítico de apropriações**: entrada e saída só se distinguem pela posição (as contas antes de
  "Total de entradas" são entradas). A coluna **Natureza** guarda isso.
- **Extrato cliente histórico**: um bloco por título; o bloco começa em "Empresa" e seus campos
  valem só para ele. Linha sem `Par` é outra baixa da mesma parcela: vira "baixa adicional", com
  `Par` e `Tipo Condição` da parcela e sem repetir o valor original. Textos como
  `*** Reparcelamento ***`, que o Sienge escreve dentro de colunas de valor, vão para **Observação**.

## Casos de borda

- Arquivo com cabeçalho, sem linhas de dados e sem total (período sem movimento): entra em
  Origem com 0 linhas e a conferência fica "OK (sem movimento)".
- Arquivo com linhas e sem o total esperado, ou total não numérico (layout mudou): conferência
  falha, sem consolidado.
- Arquivo que não abre como `.xlsx` ou sem a linha de cabeçalho esperada: sem consolidado, com o
  nome do arquivo no motivo.
- Relatório `nao_baixado` (falhou no meio): não é consolidado, para não gerar um consolidado
  parcial que pareça completo.
- Erro inesperado na consolidação: vai para o log técnico; o relatório fica `baixado` com
  "Consolidado não gerado".
- Destino com o mesmo caminho da pasta de downloads escrito de outra forma (maiúsculas, barra no
  fim): reconhecido como a mesma pasta.

## Riscos

- Layout do Sienge muda: a conferência pega e recusa o consolidado, em vez de gerar números errados.
- `vendas` com propostas ou distratos no período: a regra "VGV = Contratos + Propostas" foi
  deduzida de arquivos sem propostas. Se não valer, a conferência recusa e a regra é ajustada.
- Arquivos grandes (Extrato: ~22 mil linhas por empresa) deixam o fim da execução alguns segundos
  mais lento; a tela mostra "Consolidando...".
- Quem lia os arquivos direto da raiz de `Automação CAP` passa a encontrá-los nas subpastas.

## Plano de teste

- Fixtures sintéticas (geradas no teste, sem dados reais) com o layout de cada tipo, incluindo
  subtotais, totais desalinhados do cabeçalho (Extrato), blocos repetidos e rodapé.
- Conferência: total impresso diferente da soma → sem consolidado; diferença dentro do
  arredondamento → consolidado; contagem diferente → sem consolidado.
- Extrato: baixa adicional não repete o valor original; texto `***` vai para Observação; campos de
  um bloco não vazam para o seguinte.
- Apropriações: Natureza por posição.
- Downloads: com base igual à pasta de downloads, o arquivo é movido (não sobra cópia); com destino
  em outro lugar, é copiado para a subpasta do relatório.
- Runner: relatório `baixado` ganha o consolidado como arquivo final; recusa e erro não mudam o
  estado; `nao_baixado` não é consolidado; flag desligada não consolida.
- Conferência manual com os 29 arquivos reais da operação de 2026-10-16.

## Critérios de aceite

- Os quatro gates do CLAUDE.md passam.
- Nos 29 arquivos reais, os 7 consolidados são gerados com os totais conferidos, sem arquivo
  repetido nas pastas.

## Resultado (2026-10-16)

Implementado conforme [D18](../DECISIONS.md). Nos 29 arquivos reais: 7 consolidados, 65
conferências batendo (a maior diferença, R$ 0,02 em 224 mil, dentro do arredondamento), Extrato
com 40.112 linhas em cerca de 40 s. Processo descrito em
[processos/consolidacao_de_relatorios.md](../processos/consolidacao_de_relatorios.md).
