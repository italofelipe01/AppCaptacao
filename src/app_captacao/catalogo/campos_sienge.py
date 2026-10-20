"""Campos da tela do Sienge que cada executor preenche, conferidos na tela de cada relatorio.

E a fonte para saber se um filtro do cadastro chega ao Sienge. Um filtro casa com um campo
pelo campo identificador (com a mesma regra de busca do executor: exata, ou exata e por
sufixo ".campo") ou, quando o executor tambem aceita, por um trecho do nome. Filtro que nao
casa com nenhum campo do executor nao e aplicado.

As telas foram lidas no Sienge em 2026-10-20 (docs/auditoria-filtros-sienge.md). Os testes
conferem que os identificadores e trechos de nome daqui sao exatamente os que cada executor
procura; a auditoria (automacao/auditoria_filtros.py) confere que os campos existem na tela.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

BUSCA_EXATA = "exata"
BUSCA_SUFIXO = "sufixo"

TELA_LEGADA = "legado"
TELA_MUI = "mui"

DATA = "data"
LOOKUP = "lookup"
AUTOCOMPLETE = "autocomplete"
SELECT = "select"
CHECKBOX = "checkbox"
RADIO = "radio"

DATA_DO_DIA = "data do dia"
INICIO_DO_MES = "primeiro dia do mês"
FIM_DO_MES = "último dia do mês"


@dataclass(frozen=True)
class CampoSienge:
    rotulo: str
    """Rótulo do campo na tela do Sienge, sem o asterisco."""
    campo_tela: str
    """id ou name do campo na tela (tela MUI sem name: o rótulo)."""
    tipo: str
    identificadores: tuple[str, ...] = ()
    """Campos identificadores do cadastro que o executor aceita para este campo."""
    nomes: tuple[str, ...] = ()
    """Trechos do nome do filtro que o executor aceita quando nenhum identificador casa."""
    obrigatorio: bool = False
    """Marcado com asterisco na tela do Sienge."""
    padrao_na_tela: str = ""
    """Valor que a tela já traz preenchido, quando traz."""
    aceita_vazio: bool = False
    """O executor deixa o campo da tela como está quando o filtro vem vazio."""
    valor_fixo: str = ""
    """O executor sempre aplica este valor; o valor do cadastro não é usado."""

    @property
    def opcional_no_app(self) -> bool:
        if self.valor_fixo:
            return True
        return self.aceita_vazio and (not self.obrigatorio or bool(self.padrao_na_tela))


@dataclass(frozen=True)
class TelaSienge:
    rota: str
    """Trecho da URL do relatório no Sienge ("" quando a tela não foi localizada)."""
    busca: str
    campos: tuple[CampoSienge, ...]
    tipo_tela: str = TELA_LEGADA


def _periodo(rotulo, inicio, fim, identificadores_inicio=None, identificadores_fim=None, **extras):
    return (
        CampoSienge(f"{rotulo} (início)", inicio, DATA, identificadores_inicio or (inicio,), **extras),
        CampoSienge(f"{rotulo} (fim)", fim, DATA, identificadores_fim or (fim,), **extras),
    )


_ANALISE_COMUNS = (
    CampoSienge("Empresa", "analise.empresa.cdEmpresaView", LOOKUP, ("analise.empresa.cdEmpresaView", "cdEmpresaView"), obrigatorio=True),
    *_periodo("Período", "analise.periodoInicio", "analise.periodoFim", obrigatorio=True),
    CampoSienge("Centro de custo", "cdEmpreendView", LOOKUP, ("cdEmpreendView",)),
    CampoSienge("Correção até", "analise.dtCorrecaoAte", DATA, ("analise.dtCorrecaoAte",), obrigatorio=True, padrao_na_tela=DATA_DO_DIA),
    CampoSienge("Agrupar por", "analise.agrupar", SELECT, ("analise.agrupar",), obrigatorio=True, valor_fixo="Centro de custo"),
)

_TITULOS = (
    CampoSienge("Empresa", "empresa.cdEmpresaView", LOOKUP, ("empresa.cdEmpresaView", "cdEmpresaView")),
    CampoSienge("Centro de custo", "centroCusto.cdEmpreendView", LOOKUP, ("centroCusto.cdEmpreendView", "cdEmpreendView"), aceita_vazio=True),
    *_periodo("Período", "dtInicio", "dtFim"),
)

TELAS: dict[str, TelaSienge] = {
    "analise_resultado_sintetico": TelaSienge(
        "/common/page/354",
        BUSCA_SUFIXO,
        (
            *_ANALISE_COMUNS,
            CampoSienge("Tipo de análise", "analise.tipoAnalise", CHECKBOX, ("analise.tipoAnalise",), valor_fixo="marcado"),
        ),
    ),
    "analitico_propriedade": TelaSienge(
        "/common/page/473",
        BUSCA_SUFIXO,
        (
            *_ANALISE_COMUNS,
            CampoSienge("Tipo de análise", "tipoAnaliseRealizado", RADIO, ("tipoAnaliseRealizado",), valor_fixo="Realizado"),
        ),
    ),
    # A URL do Contas a receber não está no código nem no log: a tela não foi conferida.
    "contas_a_receber": TelaSienge(
        "",
        BUSCA_SUFIXO,
        (
            CampoSienge("Empresa", "cdEmpresaView", LOOKUP, ("cdEmpresaView",)),
            CampoSienge("Centro de custo", "cdEmpreendView", LOOKUP, ("cdEmpreendView",), aceita_vazio=True),
            *_periodo("Período de vencimento", "dtVenctoInicio", "dtVenctoFim"),
        ),
    ),
    "contas_recebidas": TelaSienge(
        "/common/page/4929",
        BUSCA_SUFIXO,
        (
            CampoSienge("Empresa", "cdEmpresaView", LOOKUP, ("cdEmpresaView",)),
            CampoSienge("Centro de custo", "cdEmpreendView", LOOKUP, ("cdEmpreendView",)),
            *_periodo("Período de recebimento", "dtRectoInicio", "dtRectoFim"),
        ),
    ),
    "extrato_cliente_historico": TelaSienge(
        "/common/page/3012",
        BUSCA_EXATA,
        (
            CampoSienge(
                "Período de vencimento (início)", "filter.dtVenctoInicio", DATA, ("filter.dtVenctoInicio",),
                obrigatorio=True, padrao_na_tela=INICIO_DO_MES,
            ),
            CampoSienge(
                "Período de vencimento (fim)", "filter.dtVenctoFim", DATA, ("filter.dtVenctoFim",),
                obrigatorio=True, padrao_na_tela=FIM_DO_MES,
            ),
            CampoSienge("Correção até", "filter.dtCorrecao", DATA, ("filter.dtCorrecao",), obrigatorio=True, padrao_na_tela=DATA_DO_DIA),
            CampoSienge("Empresa", "filter.empresa.cdEmpresaView", LOOKUP, ("filter.empresa.cdEmpresaView",)),
            CampoSienge("Centro de custo", "filter.empreend.cdEmpreendView", LOOKUP, ("filter.empreend.cdEmpreendView",)),
            CampoSienge(
                "Posição em", "dtHistorico", DATA, ("dtHistorico",), ("posicao em",),
                obrigatorio=True, padrao_na_tela=DATA_DO_DIA, aceita_vazio=True,
            ),
        ),
    ),
    "extrato_conciliado": TelaSienge(
        "/common/page/1424",
        BUSCA_SUFIXO,
        (
            CampoSienge(
                "Empresa", "entity.contaCorrente.empresa.cdEmpresaView", LOOKUP,
                ("entity.contaCorrente.empresa.cdEmpresaView", "cdEmpresaView"), obrigatorio=True,
            ),
            *_periodo("Período", "dtInicio", "dtFim", obrigatorio=True, padrao_na_tela=DATA_DO_DIA),
        ),
    ),
    "extrato_saldo_devedor_presente": TelaSienge(
        "/financeiro/contas-receber/relatorios/saldo-devedor",
        BUSCA_SUFIXO,
        (
            CampoSienge("Empresa", "Empresa", AUTOCOMPLETE, ("cdEmpresaView", "filter.empresa.cdEmpresaView"), ("empresa",)),
            CampoSienge("Vencimento início", "dataInicio", DATA, ("dtInicio", "dataInicio", "filter.dtInicioStr")),
            CampoSienge("Vencimento fim", "dataFim", DATA, ("dtFim", "dataFim", "filter.dtFimStr")),
            CampoSienge(
                "Correção até", "correcaoAte", DATA,
                ("dtCorrecao", "dataCorrecao", "filter.dtCorrecao", "filter.dtCorrecaoStr"),
                ("data de correção", "data de correcao", "corre"), padrao_na_tela=DATA_DO_DIA,
            ),
            CampoSienge(
                "Posição em", "posicaoEm", DATA,
                ("dtPosicao", "dataPosicao", "filter.dtPosicao", "filter.dtPosicaoStr"),
                ("data de posição", "data de posicao", "posi"), padrao_na_tela=DATA_DO_DIA,
            ),
        ),
        TELA_MUI,
    ),
    "mapa_venda": TelaSienge(
        "/common/page/5084",
        BUSCA_SUFIXO,
        (
            CampoSienge("Empresa", "filter.empresa.cdEmpresaView", LOOKUP, ("filter.empresa.cdEmpresaView", "cdEmpresaView")),
            CampoSienge("Empreendimento", "filter.empreend.cdEmpreendView", LOOKUP, ("filter.empreend.cdEmpreendView", "cdEmpreendView")),
            *_periodo("Período", "filter.dtInicio", "filter.dtFim"),
        ),
    ),
    "posicao_saldos": TelaSienge(
        "/common/page/1320",
        BUSCA_SUFIXO,
        (
            CampoSienge(
                "Grupo de empresa", "entity.contaCorrente.empresa.cdGrupoEmpresa", LOOKUP,
                ("entity.contaCorrente.empresa.cdGrupoEmpresa", "cdGrupoEmpresa"),
            ),
            CampoSienge(
                "Empresa", "entity.contaCorrente.empresa.cdEmpresaView", LOOKUP,
                ("entity.contaCorrente.empresa.cdEmpresaView", "cdEmpresaView"),
            ),
            CampoSienge("Data", "dtInicio", DATA, ("dtInicio",), obrigatorio=True, padrao_na_tela=DATA_DO_DIA),
        ),
    ),
    "preco_total_vendas": TelaSienge(
        "/common/page/723",
        BUSCA_SUFIXO,
        (
            CampoSienge("Empresa", "filter.empresa.cdEmpresaView", LOOKUP, ("filter.empresa.cdEmpresaView", "cdEmpresaView")),
            CampoSienge(
                "Empreendimento", "filter.empreend.cdEmpreendView", LOOKUP,
                ("filter.empreend.cdEmpreendView", "cdEmpreendView"), aceita_vazio=True,
            ),
            *_periodo("Período", "filter.dtInicioStr", "filter.dtFimStr"),
        ),
    ),
    "quadro_espelho": TelaSienge(
        "/comercial/gestao-de-unidades/quadro-espelho",
        BUSCA_SUFIXO,
        (
            CampoSienge(
                "Grupo Empresa", "Grupo Empresa", AUTOCOMPLETE,
                ("filter.grupoEmpresa.grupoEmpresaPK.cdGrupoEmpresa", "cdGrupoEmpresa", "grupoEmpresaPK.cdGrupoEmpresa"),
                ("grupo",),
            ),
            CampoSienge("Empresa", "Empresa", AUTOCOMPLETE, ("filter.empresa.cdEmpresaView", "cdEmpresaView"), ("empresa",)),
            CampoSienge(
                "Empreendimento", "Empreendimento", AUTOCOMPLETE,
                ("filter.empreend.cdEmpreendView", "cdEmpreendView"), ("empreendimento",),
            ),
        ),
        TELA_MUI,
    ),
    "relatorio_reparcelamento": TelaSienge(
        "/common/page/2458",
        BUSCA_SUFIXO,
        (
            CampoSienge("Empresa", "entity.empresa.cdEmpresaView", LOOKUP, ("entity.empresa.cdEmpresaView", "cdEmpresaView")),
            CampoSienge(
                "Centro de custo", "entity.empreend.cdEmpreendView", LOOKUP,
                ("entity.empreend.cdEmpreendView", "cdEmpreendView"), aceita_vazio=True,
            ),
            *_periodo("Período", "dtInicio", "dtFim"),
            CampoSienge("Ordenar por", "tpOrdenacao", SELECT, ("tpOrdenacao",), valor_fixo="Data reparcelamento"),
            CampoSienge("Relatório completo", "relatorioCompleto", CHECKBOX, ("relatorioCompleto",), valor_fixo="marcado"),
        ),
    ),
    "retencao": TelaSienge(
        "/common/page/1669",
        BUSCA_EXATA,
        (
            CampoSienge("Empresa", "entity.empresa.cdEmpresaView", LOOKUP, ("entity.empresa.cdEmpresaView",)),
            CampoSienge("Período (início)", "dtEmissaoInicio", DATA, ("dtEmissaoInicio",), obrigatorio=True, padrao_na_tela=INICIO_DO_MES),
            CampoSienge("Período (fim)", "dtEmissaoFim", DATA, ("dtEmissaoFim",), obrigatorio=True, padrao_na_tela=FIM_DO_MES),
        ),
    ),
    "titulos_distratados": TelaSienge("/common/page/4140", BUSCA_SUFIXO, _TITULOS),
    "titulos_quitados": TelaSienge("/common/page/4145", BUSCA_SUFIXO, _TITULOS),
    "unidades": TelaSienge(
        "/common/page/811",
        BUSCA_SUFIXO,
        (
            CampoSienge("Seleção", "filter.selecao", SELECT, ("filter.selecao",), obrigatorio=True, valor_fixo="por Empreendimento"),
            CampoSienge(
                "Grupo de empresa", "filter.grupoEmpresa.grupoEmpresaPK.cdGrupoEmpresa", LOOKUP,
                ("filter.grupoEmpresa.grupoEmpresaPK.cdGrupoEmpresa", "cdGrupoEmpresa", "grupoEmpresaPK.cdGrupoEmpresa"),
            ),
            CampoSienge(
                "Empresa", "filter.empresa.cdEmpresaView", LOOKUP,
                ("cdEmpresaView", "filter.empresa.cdEmpresaView"), obrigatorio=True,
            ),
            # Sem empreendimento o Sienge recusa: "O campo 'Empreendimento' deve ser preenchido." (2026-10-20).
            CampoSienge(
                "Empreendimento", "cdEmpreendView", LOOKUP,
                ("cdEmpreendView", "filter.empreend.cdEmpreendView"), obrigatorio=True, aceita_vazio=True,
            ),
            CampoSienge(
                "Posição em", "filter.dtHistorica", DATA, ("filter.dtHistorica", "dtHistorica"), ("posicao em",),
                obrigatorio=True, padrao_na_tela=DATA_DO_DIA, aceita_vazio=True,
            ),
        ),
    ),
    "vendas": TelaSienge(
        "/common/page/708",
        BUSCA_SUFIXO,
        (
            CampoSienge("Seleção", "filter.selecao", SELECT, ("filter.selecao",), obrigatorio=True, valor_fixo="por Empreendimento"),
            CampoSienge("Tipo de relatório", "filter.tpRelatorio", SELECT, ("filter.tpRelatorio",), obrigatorio=True, valor_fixo="Consolidado"),
            CampoSienge("Empresa", "cdEmpresaView", LOOKUP, ("cdEmpresaView", "filter.empresa.cdEmpresaView")),
            CampoSienge("Empreendimento", "cdEmpreendView", LOOKUP, ("cdEmpreendView", "filter.empreend.cdEmpreendView")),
            *_periodo("Período", "filter.dtInicioStr", "filter.dtFimStr"),
        ),
    ),
}


def normalizar(valor: object) -> str:
    """Minúsculas, sem acento e com um espaço entre as palavras."""
    texto = unicodedata.normalize("NFKD", str(valor or "").strip().lower())
    return " ".join("".join(caractere for caractere in texto if not unicodedata.combining(caractere)).split())


def _casa_identificador(tela: TelaSienge, campo: CampoSienge, filtro: dict) -> bool:
    atual = str(filtro.get("campo_identificador") or "").strip().lower()
    if not atual:
        return False
    for identificador in campo.identificadores:
        esperado = identificador.strip().lower()
        if atual == esperado or (tela.busca == BUSCA_SUFIXO and atual.endswith(f".{esperado}")):
            return True
    return False


def _casa_nome(campo: CampoSienge, filtro: dict) -> bool:
    nome = normalizar(filtro.get("nome") or filtro.get("nome_filtro"))
    return any(normalizar(trecho) in nome for trecho in campo.nomes if trecho)


def associar(executor: str, filtros: list[dict]) -> list[CampoSienge | None]:
    """Campo da tela que recebe cada filtro, na ordem dos filtros (None: o filtro não é aplicado).

    Repete a busca do executor: para cada campo vale o primeiro filtro com identificador
    aceito e, só se nenhum casar, o primeiro com um trecho de nome aceito.
    """
    associados: list[CampoSienge | None] = [None] * len(filtros)
    tela = TELAS.get(executor)
    if tela is None:
        return associados
    for campo in tela.campos:
        indice = next((i for i, filtro in enumerate(filtros) if _casa_identificador(tela, campo, filtro)), None)
        if indice is None and campo.nomes:
            indice = next((i for i, filtro in enumerate(filtros) if _casa_nome(campo, filtro)), None)
        if indice is not None and associados[indice] is None:
            associados[indice] = campo
    return associados
