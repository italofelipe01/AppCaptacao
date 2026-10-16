"""Layout de impressao de cada relatorio do Sienge que sabemos consolidar.

Cada layout foi tirado de arquivos reais exportados pelo executor. O indice da coluna nas
linhas de total vem do arquivo, nao do cabecalho: no Extrato, por exemplo, o total de
"Valor baixa" fica sob a coluna "Dias".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Conferencia:
    """Soma (ou contagem) dos dados extraidos contra um total impresso pelo Sienge."""

    descricao: str
    rotulos_total: tuple[str, ...]
    coluna_total: int
    campo: str | None = None  # None: conta as linhas de dados
    secao: str = ""  # bloco de totais em que a linha fica ("Total Geral"); vazio: qualquer
    natureza: str = ""  # Analitico de apropriacoes: so as linhas desta natureza


@dataclass(frozen=True)
class Layout:
    primeiro_campo: str  # primeira celula da linha de cabecalho da tabela
    rotulos: tuple[str, ...]  # campos do bloco de filtros que viram colunas
    conferencias: tuple[Conferencia, ...] = ()
    inicio_de_bloco: str = ""  # rotulo que abre um bloco novo e zera os campos do anterior
    natureza_por_secao: bool = False  # entradas antes de "Total de entradas", saidas antes de "Total de saidas"
    baixa_adicional: bool = False  # linha sem "Par" e outra baixa da parcela anterior
    linhas_de_total: tuple[str, ...] = ()  # linhas de total que nao comecam com "Total"


_VALORES_DISTRATO = (
    (7, "Valor histórico do contrato"),
    (8, "Valor nominal recebido"),
    (10, "Valor a devolver"),
    (11, "Valor devolvido"),
)

_TOTAIS_TITULO = (
    (9, "Saldo atual"),
    (18, "Valor baixa"),
    (24, "Acréscimo"),
    (25, "Desconto"),
    (27, "Recto líquido"),
)

LAYOUTS: dict[str, Layout] = {
    "analitico_propriedade": Layout(
        primeiro_campo="Data",
        rotulos=("Centro de custo", "Período", "Conta"),
        natureza_por_secao=True,
        conferencias=(
            Conferencia("Entradas", ("Total de entradas",), 15, "Valor", natureza="Entrada"),
            Conferencia("Saídas", ("Total de saídas",), 15, "Valor", natureza="Saída"),
        ),
    ),
    "extrato_cliente_historico": Layout(
        primeiro_campo="Par",
        rotulos=(
            "Empresa",
            "Empreendimento",
            "Cliente(s)",
            "Título",
            "Data de emissão",
            "Correção até",
            "Corretor",
            "Área privativa",
            "Documento",
            "Unidades",
        ),
        inicio_de_bloco="Empresa",
        baixa_adicional=True,
        conferencias=tuple(Conferencia(campo, ("Total título",), coluna, campo) for coluna, campo in _TOTAIS_TITULO),
    ),
    "mapa_venda": Layout(
        primeiro_campo="Contrato",
        rotulos=("Empresa", "Empreendimento", "Período"),
    ),
    "preco_total_vendas": Layout(
        primeiro_campo="Contrato",
        rotulos=("Empresa", "Empreendimento", "Período"),
        conferencias=(
            Conferencia("Vl. contrato", ("Total",), 5, "Vl. contrato"),
            Conferencia("Preço total venda", ("Total",), 6, "Preço total venda"),
        ),
    ),
    "titulos_distratados": Layout(
        primeiro_campo="Data",
        rotulos=("Empresa", "Período de distrato", "Área de negócio", "Centro de custo"),
        conferencias=tuple(
            Conferencia(campo, ("Total da empresa",), coluna, campo) for coluna, campo in _VALORES_DISTRATO
        ),
    ),
    "vendas": Layout(
        primeiro_campo="N. do contrato",
        rotulos=("Empresa", "Empreendimento", "Período do contrato"),
        linhas_de_total=("Contratos", "Propostas"),
        conferencias=(
            Conferencia(
                "Valor Geral de Venda", ("Contratos", "Propostas"), 5, "Valor Geral de Venda", secao="Total Geral"
            ),
        ),
    ),
    "unidades": Layout(
        primeiro_campo="Unidade",
        rotulos=("Empresa", "Empreendimento", "Posição em"),
        conferencias=(Conferencia("Quantidade de unidades", ("Total",), 5, secao="Total Geral"),),
    ),
}
