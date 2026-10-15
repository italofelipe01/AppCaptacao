"""Regras do catalogo: qual executor atende cada relatorio e quais filtros exigem valor.

A resolucao do executor segue esta ordem: trecho da URL, ID do relatorio e, por
fim, nome normalizado (sem acento e sem diferenca de maiusculas). Relatorio sem
executor e lacuna de configuracao, nunca motivo para cliques genericos.
"""

from __future__ import annotations

import re
import unicodedata

from app_captacao.core.shared.texto import normalize_text

# Acoes de filtro que exigem um valor digitado; as demais sao cliques/envios.
ACOES_QUE_EXIGEM_VALOR = {
    "fill",
    "fill_tab",
    "type",
    "type_tab",
    "write",
    "write_tab",
    "preencher",
    "preencher_tab",
    "send_keys",
}


def _normalizar_nome_relatorio(nome_relatorio):
    sem_acento = unicodedata.normalize("NFKD", str(nome_relatorio or ""))
    sem_acento = "".join(caractere for caractere in sem_acento if not unicodedata.combining(caractere))
    return " ".join(sem_acento.strip().lower().split())


# Nome do relatorio -> executor dedicado. Usado so quando URL e ID nao resolvem.
# As chaves sao comparadas sem acento: "Relatório" e "Relatorio" sao a mesma chave.
RELATORIOS_EXECUTORES = {
    "extratoclientehistorico": "extrato_cliente_historico",
    "extrato cliente historico": "extrato_cliente_historico",
    "relatorio de extrato de cliente": "extrato_cliente_historico",
    "extrato saldo devedor presente": "extrato_saldo_devedor_presente",
    "extrato conciliado": "extrato_conciliado",
    "relatorio extrato conciliado": "extrato_conciliado",
    "relatorio de extrato conciliado": "extrato_conciliado",
    "contas recebidas": "contas_recebidas",
    "relatorio contas recebidas": "contas_recebidas",
    "relatorio de contas recebidas": "contas_recebidas",
    "contas a receber": "contas_a_receber",
    "relatorio contas a receber": "contas_a_receber",
    "relatorio de contas a receber": "contas_a_receber",
    "analise de resultado sintetico": "analise_resultado_sintetico",
    "relatorio analise de resultado sintetico": "analise_resultado_sintetico",
    "relatorio de analise de resultado sintetico": "analise_resultado_sintetico",
    "analitico de propriedade": "analitico_propriedade",
    "analitico propriedade": "analitico_propriedade",
    "relatorio analitico de propriedade": "analitico_propriedade",
    "relatorio de analitico de propriedade": "analitico_propriedade",
    "relatorio analitico de apropriacoes": "analitico_propriedade",
    "relatorio analitico de apropriacoes7": "analitico_propriedade",
    "relatorio de analitico de apropriacoes": "analitico_propriedade",
    "analitico de apropriacoes": "analitico_propriedade",
    "analitico de apropriacoes7": "analitico_propriedade",
    "posicao de saldos": "posicao_saldos",
    "relatorio posicao de saldos": "posicao_saldos",
    "relatorio de posicao de saldos": "posicao_saldos",
    "titulos quitados": "titulos_quitados",
    "relatorio titulos quitados": "titulos_quitados",
    "relatorio de titulos quitados": "titulos_quitados",
    "titulos distratados": "titulos_distratados",
    "relatorio titulos distratados": "titulos_distratados",
    "relatorio de titulos distratados": "titulos_distratados",
    "preco total de vendas": "preco_total_vendas",
    "relatorio preco total de vendas": "preco_total_vendas",
    "relatorio de preco total de vendas": "preco_total_vendas",
    "reparcelamento": "relatorio_reparcelamento",
    "relatorio reparcelamento": "relatorio_reparcelamento",
    "relatorio de reparcelamento": "relatorio_reparcelamento",
    "mapa de venda": "mapa_venda",
    "mapa venda": "mapa_venda",
    "relatorio mapa de venda": "mapa_venda",
    "relatorio de mapa de venda": "mapa_venda",
    "quadro espelho": "quadro_espelho",
    "relatorio quadro espelho": "quadro_espelho",
    "relatorio de quadro espelho": "quadro_espelho",
    "retencao": "retencao",
    "retencao impostos": "retencao",
    "unidades": "unidades",
    "relatorio de unidades": "unidades",
    "vendas": "vendas",
    "relatorio de vendas": "vendas",
}

_EXECUTORES_POR_NOME = {_normalizar_nome_relatorio(nome): executor for nome, executor in RELATORIOS_EXECUTORES.items()}


RELATORIOS_EXECUTORES_RELATORIO = {
    7: "extrato_cliente_historico",
    2: "extrato_saldo_devedor_presente",
    6: "extrato_conciliado",
    8: "contas_recebidas",
    10: "analise_resultado_sintetico",
    11: "posicao_saldos",
    3: "vendas",
    12: "titulos_quitados",
    14: "preco_total_vendas",
}


RELATORIOS_EXECUTORES_URL = {
    "/common/page/3012": "extrato_cliente_historico",
    "/financeiro/contas-receber/relatorios/saldo-devedor": "extrato_saldo_devedor_presente",
    "/common/page/1424": "extrato_conciliado",
    "/common/page/4929": "contas_recebidas",
    "/common/page/354": "analise_resultado_sintetico",
    "/common/page/1320": "posicao_saldos",
    "/common/page/1669": "retencao",
    "/common/page/4145": "titulos_quitados",
    "/common/page/4140": "titulos_distratados",
    "/common/page/2458": "relatorio_reparcelamento",
    "/common/page/5084": "mapa_venda",
    "/comercial/gestao-de-unidades/quadro-espelho": "quadro_espelho",
    "/common/page/708": "vendas",
    "/common/page/723": "preco_total_vendas",
}

# O trecho precisa terminar a rota: "/common/page/723" nao casa com "/common/page/7230".
_FIM_DO_TRECHO_URL = r"(?![0-9a-z_-])"


# Filtros que o executor preenche sozinho com valor fixo: a tela nao pede o valor
# e a validacao nao cobra. Executor -> campo (minusculo) -> valor.
FILTROS_FIXOS_POR_EXECUTOR = {
    "unidades": {"filter.selecao": "por Empreendimento"},
}


def _inteiro_ou_none(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _executor_pela_url(url_relatorio):
    url_normalizada = str(url_relatorio or "").strip().lower()
    for trecho_url, executor in RELATORIOS_EXECUTORES_URL.items():
        if re.search(re.escape(trecho_url) + _FIM_DO_TRECHO_URL, url_normalizada):
            return executor
    return ""


def _executor_pelo_nome(nome_relatorio):
    nome = _normalizar_nome_relatorio(nome_relatorio)
    if not nome:
        return ""
    compacto = nome.replace(" ", "")
    if nome in _EXECUTORES_POR_NOME:
        return _EXECUTORES_POR_NOME[nome]
    if compacto in _EXECUTORES_POR_NOME:
        return _EXECUTORES_POR_NOME[compacto]

    # Nome com texto a mais: vence a chave mais longa ("preco total de vendas", nao "vendas").
    candidatos = [
        (len(chave), executor)
        for chave, executor in _EXECUTORES_POR_NOME.items()
        if re.search(rf"\b{re.escape(chave)}\b", nome) or chave.replace(" ", "") in compacto
    ]
    if not candidatos:
        return ""
    return max(candidatos, key=lambda candidato: candidato[0])[1]


def obter_executor_relatorio(nome_relatorio, id_relatorio=None, url_relatorio=""):
    executor = _executor_pela_url(url_relatorio)
    if executor:
        return executor

    id_relatorio = _inteiro_ou_none(id_relatorio)
    if id_relatorio in RELATORIOS_EXECUTORES_RELATORIO:
        return RELATORIOS_EXECUTORES_RELATORIO[id_relatorio]

    return _executor_pelo_nome(nome_relatorio)


def executor_do_relatorio(relatorio: dict) -> str:
    """Executor de um relatorio vindo do catalogo, da operacao ou do payload de execucao."""
    return obter_executor_relatorio(
        relatorio.get("nome") or relatorio.get("nome_relatorio") or "",
        relatorio.get("id") or relatorio.get("id_relatorio"),
        relatorio.get("url") or relatorio.get("url_relatorio") or "",
    )


def valor_fixo_do_filtro(executor: str, filtro: dict) -> str:
    campo = normalize_text(filtro.get("campo_identificador")).lower()
    return FILTROS_FIXOS_POR_EXECUTOR.get(executor, {}).get(campo, "")


def aplicar_filtros_fixos(relatorio: dict) -> dict:
    """Preenche os filtros de valor fixo do executor e os marca como automaticos."""
    executor = executor_do_relatorio(relatorio)
    for filtro in relatorio.get("filtros", []):
        valor = valor_fixo_do_filtro(executor, filtro)
        if valor:
            filtro.update(valor=valor, valor_fixo=valor, opcional=True, automatico=True, tipo_campo_valor="CLICK")
    return relatorio


def eh_filtro_opcional_relatorio(relatorio, filtro):
    executor = executor_do_relatorio(relatorio)
    campo = str(filtro.get("campo_identificador") or "").strip().lower()

    if executor in {
        "titulos_quitados",
        "titulos_distratados",
        "relatorio_reparcelamento",
        "contas_a_receber",
    }:
        return campo in {
            "centrocusto.cdempreendview",
            "entity.empreend.cdempreendview",
            "cdempreendview",
        }

    if executor == "preco_total_vendas":
        return campo in {"filter.empreend.cdempreendview", "cdempreendview"}

    if executor == "unidades":
        return campo in {"filter.empreend.cdempreendview", "cdempreendview"}

    return False


def normalizar_acao(acao):
    return (acao or "").strip().lower()


def acao_exige_valor(acao):
    """Acao vazia conta como preenchimento (o padrao do Sienge e digitar e dar TAB)."""
    acao_normalizada = normalizar_acao(acao)
    if not acao_normalizada:
        return True
    return acao_normalizada in ACOES_QUE_EXIGEM_VALOR


def filtros_obrigatorios_sem_valor(relatorio: dict) -> list[str]:
    """Nomes dos filtros que exigem valor e chegaram vazios, exceto os opcionais do executor."""
    missing = []
    for filtro in relatorio.get("filtros", []):
        valor = normalize_text(filtro.get("valor"))
        if eh_filtro_opcional_relatorio(relatorio, filtro):
            continue
        if acao_exige_valor(filtro.get("acao")) and not valor:
            missing.append(normalize_text(filtro.get("nome")) or f"Filtro {filtro.get('id')}")
    return missing
