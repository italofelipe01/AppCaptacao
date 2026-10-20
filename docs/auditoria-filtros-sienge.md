# Auditoria dos filtros no Sienge

Telas lidas no Sienge em 20/10/2026, 10:21–10:25, com a leitura da ferramenta
`tools/auditar_filtros_sienge.py` (o Saldo devedor com o modal de datas aberto; o Quadro espelho
na aba Lista; Unidades e Vendas depois da Seleção "por Empreendimento"). A rodada completa da
ferramenta às 10:54 não passou do login: o botão "Entrar com Sienge ID" deixou de responder. O
cadastro não foi lido (banco indisponível), então a divergência (a) não foi avaliada: rode a
ferramenta de novo com o banco no ar.

## Corrigido nesta rodada

- **Unidades:** o executor procurava `filter.dtInicioStr`, `filter.dtFimStr` e `filter.tpRelatorio`,
  que não existem na tela (o select custava 42 s por execução); saíram. O Empreendimento passou a
  ser obrigatório no app: sem ele o Sienge recusa com "O campo 'Empreendimento' deve ser
  preenchido.". A "Posição em" (`filter.dtHistorica`) já tinha sido corrigida no mesmo dia.
- **Extrato cliente histórico:** a tela tem "Posição em*" (`dtHistorico`, padrão = data do dia), que
  o executor ignorava; agora é preenchida e conferida na tela.
- **Analítico de apropriações:** "Correção até*" existe na tela, mas o executor não lia o filtro;
  agora aplica como o Análise de resultado sintético.
- **Quadro espelho:** o executor procurava datas (`filter.dtInicio`/`filter.dtFim`) que a tela não
  tem, nem na aba Lista; saíram.
- **Contas a receber:** a URL não está no código nem no log; a tela não foi conferida.

Divergências: (a) filtro do cadastro sem campo na tela; (b) campo declarado que não existe na
tela; (c) campo obrigatório da tela, sem padrão, que nenhum filtro preenche; (d) obrigatoriedade
ou padrão da declaração diferente da tela. Regras em
[specs/filtros-validados-no-sienge.md](specs/filtros-validados-no-sienge.md).

## Resumo

| Executor | Tela | Campos declarados | Divergências |
| --- | --- | --- | --- |
| `analise_resultado_sintetico` | `/common/page/354` | 7 | 0 |
| `analitico_propriedade` | `/common/page/473` | 7 | 0 |
| `contas_a_receber` | `—` | 4 | — (tela não localizada (sem URL no código e no cadastro)) |
| `contas_recebidas` | `/common/page/4929` | 4 | 0 |
| `extrato_cliente_historico` | `/common/page/3012` | 6 | 0 |
| `extrato_conciliado` | `/common/page/1424` | 3 | 0 |
| `extrato_saldo_devedor_presente` | `/financeiro/contas-receber/relatorios/saldo-devedor` | 5 | 0 |
| `mapa_venda` | `/common/page/5084` | 4 | 0 |
| `posicao_saldos` | `/common/page/1320` | 3 | 0 |
| `preco_total_vendas` | `/common/page/723` | 4 | 0 |
| `quadro_espelho` | `/comercial/gestao-de-unidades/quadro-espelho` | 3 | 0 |
| `relatorio_reparcelamento` | `/common/page/2458` | 6 | 0 |
| `retencao` | `/common/page/1669` | 3 | 0 |
| `titulos_distratados` | `/common/page/4140` | 4 | 0 |
| `titulos_quitados` | `/common/page/4145` | 4 | 0 |
| `unidades` | `/common/page/811` | 5 | 0 |
| `vendas` | `/common/page/708` | 6 | 0 |

## analise_resultado_sintetico

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Empresa | `analise.empresa.cdEmpresaView` | lookup | sim | — | não | ok |
| Período (início) | `analise.periodoInicio` | data | sim | — | não | ok |
| Período (fim) | `analise.periodoFim` | data | sim | — | não | ok |
| Centro de custo | `cdEmpreendView` | lookup | não | — | não | ok |
| Correção até | `analise.dtCorrecaoAte` | data | sim | data do dia | não | ok |
| Agrupar por | `analise.agrupar` | select | sim | fixo: Centro de custo | sim | ok |
| Tipo de análise | `analise.tipoAnalise` | checkbox | não | fixo: marcado | sim | ok |

## analitico_propriedade

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Empresa | `analise.empresa.cdEmpresaView` | lookup | sim | — | não | ok |
| Período (início) | `analise.periodoInicio` | data | sim | — | não | ok |
| Período (fim) | `analise.periodoFim` | data | sim | — | não | ok |
| Centro de custo | `cdEmpreendView` | lookup | não | — | não | ok |
| Correção até | `analise.dtCorrecaoAte` | data | sim | data do dia | não | ok |
| Agrupar por | `analise.agrupar` | select | sim | fixo: Centro de custo | sim | ok |
| Tipo de análise | `tipoAnaliseRealizado` | radio | não | fixo: Realizado | sim | ok |

## contas_a_receber

Não auditado: tela não localizada (sem URL no código e no cadastro).

## contas_recebidas

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Empresa | `cdEmpresaView` | lookup | não | — | não | ok |
| Centro de custo | `cdEmpreendView` | lookup | não | — | não | ok |
| Período de recebimento (início) | `dtRectoInicio` | data | não | — | não | ok |
| Período de recebimento (fim) | `dtRectoFim` | data | não | — | não | ok |

## extrato_cliente_historico

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Período de vencimento (início) | `filter.dtVenctoInicio` | data | sim | primeiro dia do mês | não | ok |
| Período de vencimento (fim) | `filter.dtVenctoFim` | data | sim | último dia do mês | não | ok |
| Correção até | `filter.dtCorrecao` | data | sim | data do dia | não | ok |
| Empresa | `filter.empresa.cdEmpresaView` | lookup | não | — | não | ok |
| Centro de custo | `filter.empreend.cdEmpreendView` | lookup | não | — | não | ok |
| Posição em | `dtHistorico` | data | sim | data do dia | sim | ok |

## extrato_conciliado

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Empresa | `entity.contaCorrente.empresa.cdEmpresaView` | lookup | sim | — | não | ok |
| Período (início) | `dtInicio` | data | sim | data do dia | não | ok |
| Período (fim) | `dtFim` | data | sim | data do dia | não | ok |

## extrato_saldo_devedor_presente

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Empresa | `Empresa` | autocomplete | não | — | não | ok |
| Vencimento início | `dataInicio` | data | não | — | não | ok |
| Vencimento fim | `dataFim` | data | não | — | não | ok |
| Correção até | `correcaoAte` | data | não | data do dia | não | ok |
| Posição em | `posicaoEm` | data | não | data do dia | não | ok |

## mapa_venda

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Empresa | `filter.empresa.cdEmpresaView` | lookup | não | — | não | ok |
| Empreendimento | `filter.empreend.cdEmpreendView` | lookup | não | — | não | ok |
| Período (início) | `filter.dtInicio` | data | não | — | não | ok |
| Período (fim) | `filter.dtFim` | data | não | — | não | ok |

## posicao_saldos

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Grupo de empresa | `entity.contaCorrente.empresa.cdGrupoEmpresa` | lookup | não | — | não | ok |
| Empresa | `entity.contaCorrente.empresa.cdEmpresaView` | lookup | não | — | não | ok |
| Data | `dtInicio` | data | sim | data do dia | não | ok |

## preco_total_vendas

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Empresa | `filter.empresa.cdEmpresaView` | lookup | não | — | não | ok |
| Empreendimento | `filter.empreend.cdEmpreendView` | lookup | não | — | sim | ok |
| Período (início) | `filter.dtInicioStr` | data | não | — | não | ok |
| Período (fim) | `filter.dtFimStr` | data | não | — | não | ok |

## quadro_espelho

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Grupo Empresa | `Grupo Empresa` | autocomplete | não | — | não | ok |
| Empresa | `Empresa` | autocomplete | não | — | não | ok |
| Empreendimento | `Empreendimento` | autocomplete | não | — | não | ok |

## relatorio_reparcelamento

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Empresa | `entity.empresa.cdEmpresaView` | lookup | não | — | não | ok |
| Centro de custo | `entity.empreend.cdEmpreendView` | lookup | não | — | sim | ok |
| Período (início) | `dtInicio` | data | não | — | não | ok |
| Período (fim) | `dtFim` | data | não | — | não | ok |
| Ordenar por | `tpOrdenacao` | select | não | fixo: Data reparcelamento | sim | ok |
| Relatório completo | `relatorioCompleto` | checkbox | não | fixo: marcado | sim | ok |

## retencao

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Empresa | `entity.empresa.cdEmpresaView` | lookup | não | — | não | ok |
| Período (início) | `dtEmissaoInicio` | data | sim | primeiro dia do mês | não | ok |
| Período (fim) | `dtEmissaoFim` | data | sim | último dia do mês | não | ok |

## titulos_distratados

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Empresa | `empresa.cdEmpresaView` | lookup | não | — | não | ok |
| Centro de custo | `centroCusto.cdEmpreendView` | lookup | não | — | sim | ok |
| Período (início) | `dtInicio` | data | não | — | não | ok |
| Período (fim) | `dtFim` | data | não | — | não | ok |

## titulos_quitados

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Empresa | `empresa.cdEmpresaView` | lookup | não | — | não | ok |
| Centro de custo | `centroCusto.cdEmpreendView` | lookup | não | — | sim | ok |
| Período (início) | `dtInicio` | data | não | — | não | ok |
| Período (fim) | `dtFim` | data | não | — | não | ok |

## unidades

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Seleção | `filter.selecao` | select | sim | fixo: por Empreendimento | sim | ok |
| Grupo de empresa | `filter.grupoEmpresa.grupoEmpresaPK.cdGrupoEmpresa` | lookup | não | — | não | ok |
| Empresa | `filter.empresa.cdEmpresaView` | lookup | sim | — | não | ok |
| Empreendimento | `cdEmpreendView` | lookup | sim | — | não | ok |
| Posição em | `filter.dtHistorica` | data | sim | data do dia | sim | ok |

## vendas

| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |
| --- | --- | --- | --- | --- | --- | --- |
| Seleção | `filter.selecao` | select | sim | fixo: por Empreendimento | sim | ok |
| Tipo de relatório | `filter.tpRelatorio` | select | sim | fixo: Consolidado | sim | ok |
| Empresa | `cdEmpresaView` | lookup | não | — | não | ok |
| Empreendimento | `cdEmpreendView` | lookup | não | — | não | ok |
| Período (início) | `filter.dtInicioStr` | data | não | — | não | ok |
| Período (fim) | `filter.dtFimStr` | data | não | — | não | ok |
