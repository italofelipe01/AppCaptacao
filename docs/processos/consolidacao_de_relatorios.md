# Consolidação dos relatórios

Código em [consolidacao/](../../src/app_captacao/consolidacao/), chamado no fim da execução por
[execucao/runner.py](../../src/app_captacao/execucao/runner.py). Spec:
[specs/consolidacao-relatorios.md](../specs/consolidacao-relatorios.md).

## O que sai

Para cada relatório `baixado` com layout conhecido, na pasta do relatório
(`<base>\<Relatório>\`, ver [downloads_e_destino.md](downloads_e_destino.md)):

```text
Automação CAP\
└── Unidades\
    ├── Unidades_101_2026-10-16.xlsx
    ├── Unidades_242_2026-10-16.xlsx
    ├── Unidades_242_2026-10-16_2.xlsx        (outro empreendimento da mesma empresa)
    └── Unidades_consolidado_2026-10-16.xlsx
```

O consolidado tem três abas:

| Aba | Conteúdo |
| --- | --- |
| Dados | Uma tabela plana: `Arquivo de origem`, os campos do bloco de filtros do Sienge (Empresa, Empreendimento, Período...) como colunas e as colunas do relatório. Datas viram data do Excel. |
| Origem | Cada arquivo, com empresa, empreendimento/centro de custo e quantidade de linhas. |
| Conferência | Cada total conferido: valor extraído, valor impresso pelo Sienge e situação. |

Só entram os arquivos daquela execução. Relatório `nao_baixado` não é consolidado. Nada é
sobrescrito: um segundo consolidado no mesmo dia ganha `_2`.

## Como o arquivo é lido

O Sienge exporta no layout de impressão: título, bloco de filtros, cabeçalho, dados, subtotais,
totais e rodapé ("16/10/2026 - 09:11:55 | SIENGE / STARIAN"). A leitura
([leitura.py](../../src/app_captacao/consolidacao/leitura.py)):

1. Acha a linha de cabeçalho pela primeira célula (`Data`, `Par`, `Contrato`...). Sem ela, o
   arquivo é recusado.
2. Fora da tabela, lê os rótulos do bloco de filtros do layout; o valor é a próxima célula
   preenchida à direita.
3. Linha em branco ou rodapé fecha a tabela. Linha que começa com `Total`, `Diferença` ou `**`
   é guardada como total, não como dado. `Total Geral | Valor | Quantidade` (só texto) abre um
   bloco de totais.
4. As colunas de cada tipo, os rótulos e as conferências ficam em
   [layouts.py](../../src/app_captacao/consolidacao/layouts.py).

Particularidades:

- **Analítico de apropriações**: entrada e saída só se distinguem pela posição; as contas antes
  de "Total de entradas" ganham `Natureza = Entrada`, as antes de "Total de saídas", `Saída`.
- **Extrato cliente histórico**: um bloco por título, aberto por "Empresa"; os campos de um
  título não passam para o seguinte. Linha sem `Par` é outra baixa da parcela anterior
  (`Linha = Baixa adicional`, com `Par` e `Tipo Condição` da parcela e sem o valor original).
  `*** Reparcelamento ***` e afins saem da coluna de valor e vão para `Observação`.

## Conferência

Cada arquivo é conferido contra os totais que o Sienge imprime nele
([consolidador.py](../../src/app_captacao/consolidacao/consolidador.py)). O índice da coluna na
linha de total vem do arquivo real: no Extrato, "Total título" traz Saldo atual na coluna 9 e
Valor baixa na 18, enquanto os dados ficam na 15 e na 21.

- Soma: aceita até R$ 0,005 por linha somada (mínimo R$ 0,01). Cada valor exportado vem
  arredondado em 2 casas, e o Sienge soma antes de arredondar (num arquivo real de apropriações,
  as linhas somam 224.383,67 e o total impresso é 224.383,65).
- Contagem (Unidades): precisa bater exatamente.
- Sem linhas e sem total: período sem movimento, OK.
- Qualquer divergência, total ausente ou total sem número na coluna esperada: **o consolidado
  não é gerado**, e o motivo vai para a mensagem do relatório. Os arquivos originais não mudam.

## Na tela

O relatório continua `baixado`. A mensagem ganha "Consolidado: <arquivo>, N linha(s), conferido
com os totais do Sienge" ou "Consolidado nao gerado: <motivo>", e o consolidado vira o "Arquivo
final". Durante a consolidação, o resumo mostra "Consolidando <relatório> (i/n)". O resumo final
diz quantos foram gerados.

## Como adicionar um relatório

1. Exporte um arquivo real e ache: a primeira célula do cabeçalho, os rótulos do bloco de
   filtros e as linhas de total com o índice de cada coluna.
2. Acrescente o `Layout` em `layouts.py`, com a chave do executor em `catalogo/regras.py`.
3. Crie a planilha sintética em `tests/consolidacao/planilhas_sienge.py` com os mesmos índices e
   teste a leitura e uma conferência que falha.
4. Rode a consolidação contra os arquivos reais e confira a aba Conferência.

## Desligar

`APP_CONSOLIDAR_RELATORIOS=false` no `.env`. As pastas por relatório continuam.
