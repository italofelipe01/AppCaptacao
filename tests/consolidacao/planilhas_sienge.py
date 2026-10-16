"""Planilhas sinteticas no layout de impressao do Sienge (sem dados reais).

As colunas usam os mesmos indices dos arquivos exportados: no Extrato, por exemplo, o total
de "Valor baixa" fica na coluna 18, e o dado, na 21.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

VAZIA = {0: " "}  # linha em branco que o openpyxl grava (sem celula a linha some)
RODAPE = {0: "16/10/2026 - 09:11:55", 7: "SIENGE / STARIAN"}


def gravar(caminho: Path, linhas: list[dict], largura: int) -> Path:
    livro = Workbook()
    aba = livro.active
    assert aba is not None
    aba.title = "Relatório"
    for celulas in linhas:
        linha = [None] * largura
        for indice, valor in celulas.items():
            linha[indice] = valor
        aba.append(linha)
    livro.save(caminho)
    return caminho


def analitico(caminho: Path, centro="1002 - OBRA TESTE", total_saidas=1.0) -> Path:
    cabecalho = {0: "Data", 1: "Documento", 5: "Or", 6: "Lanc.", 8: "Complemento", 12: "Vl. total titulo", 15: "Valor"}
    linhas = [
        VAZIA,
        {3: "Analítico de Apropriações"},
        VAZIA,
        {0: "Analítico de apropriações por", 4: "Centro de custo"},
        {0: "Período", 4: "01/08/2026 até 30/09/2026", 9: "Seleção por", 13: "Data de vencimento/pagamento"},
        {0: "Centro de custo", 4: centro},
        VAZIA,
        {0: "Conta", 2: "1.01 - Receita de vendas", 14: "Tipo", 15: "Resultado"},
        cabecalho,
        {0: "03/08/2026", 1: "REC.1", 5: "CR", 8: "Recebimento A", 12: 100.0, 15: 100.0},
        {0: "04/08/2026", 1: "REC.2", 5: "CR", 8: "Recebimento B", 12: 50.25, 15: 50.25},
        {0: "Total da conta", 15: 150.25},
        VAZIA,
        {0: "Total de entradas", 15: 150.25},
        VAZIA,
        {0: "Conta", 2: "2.12 - Tarifas bancárias", 14: "Tipo", 15: "Resultado"},
        cabecalho,
        {0: "05/08/2026", 1: "AV.SN", 5: "BC", 8: "Tarifa", 12: 1.0, 15: 1.0},
        {0: "Total da conta", 15: 1.0},
        VAZIA,
        {0: "Total de saídas", 15: total_saidas},
        VAZIA,
        {0: "Diferença (Entradas - Saídas)", 15: 149.25},
        VAZIA,
        RODAPE,
    ]
    return gravar(caminho, linhas, 17)


_CABECALHO_EXTRATO = {
    0: "Par", 1: "Tipo Condição", 6: "Dt. base", 7: "Valor original", 9: "Data vencto", 12: "Id",
    13: "Dt. cálculo", 15: "Saldo atual", 18: "Dias", 19: "Data baixa", 21: "Valor baixa",
    24: "Acréscimo", 25: "Desconto", 27: "Recto líquido",
}


def _bloco_extrato(titulo, cliente, parcelas, total, corretor=None) -> list[dict]:
    bloco = [
        {0: "Empresa", 3: "SPE TESTE LTDA (101)", 14: "Empreendimento", 18: "OBRA TESTE (1330)"},
        {0: "Cliente(s)", 3: cliente},
        {0: "Título", 3: titulo, 14: "Data de emissão", 18: "10/12/2012"},
        {0: "Correção até", 3: "30/09/2026"},
    ]
    if corretor:
        bloco.append({0: "Corretor", 3: corretor})
    bloco += [
        {0: "Área privativa", 3: 89.2},
        {0: "Documento", 3: f"CT.APTO {titulo}", 14: "Unidades", 18: f"Apto {titulo}"},
        VAZIA,
        _CABECALHO_EXTRATO,
        *parcelas,
        {0: "Total data base", 7: total[0], 9: total[1], 18: total[2], 24: total[3], 25: total[4], 27: total[5]},
        {0: "Total título", 7: total[0], 9: total[1], 18: total[2], 24: total[3], 25: total[4], 27: total[5]},
        VAZIA,
        {0: "Contrato"},
        {0: "(C) - Parcela enviada para a cobrança"},
        VAZIA,
    ]
    return bloco


def extrato(caminho: Path, total_recto_titulo_1=1501.5) -> Path:
    parcelas_1 = [
        {0: 1, 1: "ATO", 6: "01/12/2012", 7: 1000.0, 9: "08/02/2013", 12: 0, 13: "01/09/2026", 15: 0,
         18: 14, 19: "22/02/2013", 21: 1000.0, 24: 0, 25: 0, 27: 1000.0},
        {0: 2, 1: "PARCELAS MENSAIS", 6: "01/12/2012", 7: 500.0, 9: "20/02/2013", 12: 10, 13: "01/09/2026", 15: 0,
         18: 9, 19: "01/03/2013", 21: 300.0, 24: 1.0, 25: 0, 27: 301.0},
        # Outra baixa da parcela 2: sem Par, sem valor original.
        {18: 22, 19: "14/03/2013", 21: 200.0, 24: 0.5, 25: 0, 27: 200.5},
        {0: 3, 1: "PARCELAS MENSAIS", 6: "01/12/2012", 7: 500.0, 9: "20/03/2013", 12: 10, 13: "01/09/2026", 15: 0,
         18: 0, 19: "01/03/2013", 21: 510.0, 24: "*** Reparcelamento ***"},
    ]
    parcelas_2 = [
        {0: 1, 1: "FINANCIAMENTO", 6: "01/10/2015", 7: 250.0, 9: "01/01/2016", 12: 22, 13: "01/09/2026", 15: 250.0,
         18: 0, 21: 0, 24: 0, 25: 0, 27: 0},
    ]
    linhas = [
        VAZIA,
        {5: "Extrato Cliente Histórico"},
        VAZIA,
        *_bloco_extrato(1, "CLIENTE A(1)", parcelas_1, (2000.0, 0, 2010.0, 1.5, 0, total_recto_titulo_1), "CORRETORA X"),
        *_bloco_extrato(2, "CLIENTE B(2)", parcelas_2, (250.0, 250.0, 0, 0, 0, 0)),
        RODAPE,
    ]
    return gravar(caminho, linhas, 28)


def unidades(caminho: Path, empreendimento="1002 - OBRA TESTE", total_unidades=3) -> Path:
    linhas = [
        VAZIA,
        {3: "Unidades por Empreendimento"},
        VAZIA,
        {0: "Empresa", 4: "242 - SPE TESTE LTDA"},
        {0: "Empreendimento", 4: empreendimento},
        {0: "Posição em", 4: "16/10/2026"},
        VAZIA,
        {0: "Unidade", 1: "Tipo", 7: "Área privativa", 15: "Valor atual", 16: "Contrato", 19: "Cliente",
         21: "Prev. ent.", 22: "Estoque Comercial"},
        {0: "Apto 101", 1: "2Q", 7: 60.5, 15: 0, 16: "APTO 101", 19: "1 - CLIENTE A", 21: "30/06/2015", 22: "Vendida"},
        {0: "Apto 102", 1: "2Q", 7: 60.5, 15: 0, 22: "Disponível"},
        {0: "Apto 103", 1: "3Q", 7: 80.0, 15: 0, 22: "Disponível"},
        VAZIA,
        {0: "Totais do Empreendimento", 5: "Quantidade de unidades", 8: "Área"},
        {0: "Unidades Vendidas", 5: 1, 8: 60.5},
        {0: "Total", 5: 3, 8: 201.0},
        VAZIA,
        {0: "Total Geral", 5: "Quantidade de unidades", 8: "Área"},
        {0: "Unidades Vendidas", 5: 1, 8: 60.5},
        {0: "Total", 5: total_unidades, 8: 201.0},
        VAZIA,
        {0: "(*) - Proposta de Venda"},
        VAZIA,
        RODAPE,
    ]
    return gravar(caminho, linhas, 23)


def preco_total(caminho: Path, valores=(100.0, 200.0), total_contrato=None) -> Path:
    total = sum(valores) if total_contrato is None else total_contrato
    linhas = [
        VAZIA,
        {2: "Preço Total de Vendas"},
        VAZIA,
        {0: "Empresa", 3: "101 - SPE TESTE LTDA"},
        {0: "Empreendimento", 3: "1330 - OBRA TESTE"},
        {0: "Período", 3: "01/01/2000 a 30/09/2026"},
        VAZIA,
        {0: "Contrato", 1: "Dt. emissão", 3: "Cliente", 5: "Vl. contrato", 6: "Preço total venda", 8: "Área", 9: "Unidade"},
        *[
            {0: f"APTO {i}", 1: "08/12/2012", 3: f"{i} - CLIENTE", 5: v, 6: v, 8: 50.0, 9: f"Apto {i}"}
            for i, v in enumerate(valores, start=1)
        ],
        {0: "Total", 5: total, 6: sum(valores)},
        VAZIA,
        RODAPE,
    ]
    return gravar(caminho, linhas, 10)


def mapa_vendas(caminho: Path) -> Path:
    linhas = [
        VAZIA,
        {3: "Mapa de Vendas"},
        VAZIA,
        {0: "Empresa", 5: "242 - SPE TESTE LTDA"},
        {0: "Empreendimento", 5: "1002 - OBRA TESTE"},
        {0: "Período", 5: "01/08/2026 a 30/09/2026"},
        VAZIA,
        {0: "Contrato", 1: "Unidade", 6: "Cliente", 16: "Data da Venda", 17: "Valor da Venda", 21: "Saldo Devedor"},
        {0: 2244025672, 1: "01A", 6: "1 - CLIENTE A", 16: "22/08/2026", 17: 323175, 21: 180000},
        VAZIA,
        RODAPE,
    ]
    return gravar(caminho, linhas, 22)
