def _normalizar_nome_relatorio(nome_relatorio):
    return " ".join(str(nome_relatorio or "").strip().lower().split())


RELATORIOS_BOTOES = {
    "extratoclientehistorico": [],
}

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
    "relatório analítico de apropriações": "analitico_propriedade",
    "relatório analítico de apropriações7": "analitico_propriedade",
    "relatório de analítico de apropriações": "analitico_propriedade",
    "analítico de apropriações": "analitico_propriedade",
    "analítico de apropriações7": "analitico_propriedade",
    "posicao de saldos": "posicao_saldos",
    "posicao de saldos": "posicao_saldos",
    "relatorio posicao de saldos": "posicao_saldos",
    "relatorio de posicao de saldos": "posicao_saldos",
    "relatorio de posicao de saldos": "posicao_saldos",
    "titulos quitados": "titulos_quitados",
    "titulos quitados": "titulos_quitados",
    "relatorio titulos quitados": "titulos_quitados",
    "relatorio de titulos quitados": "titulos_quitados",
    "relatorio de titulos quitados": "titulos_quitados",
    "titulos distratados": "titulos_distratados",
    "titulos distratados": "titulos_distratados",
    "relatorio titulos distratados": "titulos_distratados",
    "relatorio de titulos distratados": "titulos_distratados",
    "relatorio de titulos distratados": "titulos_distratados",
    "preco total de vendas": "preco_total_vendas",
    "preco total de vendas": "preco_total_vendas",
    "relatorio preco total de vendas": "preco_total_vendas",
    "relatorio de preco total de vendas": "preco_total_vendas",
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

RELATORIOS_EXECUTORES_OPERACAO = {
    7: "extrato_cliente_historico",
}

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


def listar_relatorios_com_botoes():
    return {
        nome_relatorio: [dict(botao) for botao in botoes]
        for nome_relatorio, botoes in RELATORIOS_BOTOES.items()
    }


def obter_botoes_relatorio(nome_relatorio):
    nome_normalizado = _normalizar_nome_relatorio(nome_relatorio)
    if nome_normalizado in RELATORIOS_BOTOES:
        return [dict(botao) for botao in RELATORIOS_BOTOES[nome_normalizado]]

    for chave_relatorio, botoes in RELATORIOS_BOTOES.items():
        if chave_relatorio in nome_normalizado:
            return [dict(botao) for botao in botoes]

    return []


def obter_executor_relatorio(nome_relatorio, id_relatorio_operacao=None, id_relatorio=None, url_relatorio=""):
    try:
        id_relatorio_operacao = int(id_relatorio_operacao)
    except (TypeError, ValueError):
        id_relatorio_operacao = None

    try:
        id_relatorio = int(id_relatorio)
    except (TypeError, ValueError):
        id_relatorio = None

    if id_relatorio_operacao in RELATORIOS_EXECUTORES_OPERACAO:
        return RELATORIOS_EXECUTORES_OPERACAO[id_relatorio_operacao]

    url_normalizada = str(url_relatorio or "").strip().lower()
    for trecho_url, executor in RELATORIOS_EXECUTORES_URL.items():
        if trecho_url in url_normalizada:
            return executor

    if id_relatorio in RELATORIOS_EXECUTORES_RELATORIO:
        return RELATORIOS_EXECUTORES_RELATORIO[id_relatorio]

    nome_normalizado = _normalizar_nome_relatorio(nome_relatorio)
    nome_compacto = nome_normalizado.replace(" ", "")
    if nome_normalizado in RELATORIOS_EXECUTORES:
        return RELATORIOS_EXECUTORES[nome_normalizado]

    if nome_compacto in RELATORIOS_EXECUTORES:
        return RELATORIOS_EXECUTORES[nome_compacto]

    for chave_relatorio, executor in RELATORIOS_EXECUTORES.items():
        chave_compacta = chave_relatorio.replace(" ", "")
        if chave_relatorio in nome_normalizado or chave_compacta in nome_compacto:
            return executor

    return ""


def anexar_botoes_automaticos(relatorio):
    if not relatorio:
        return relatorio

    filtros_existentes = relatorio.setdefault("filtros", [])
    ids_existentes = {filtro.get("id") for filtro in filtros_existentes}

    for botao in obter_botoes_relatorio(relatorio.get("nome")):
        if botao.get("id") in ids_existentes:
            continue
        filtros_existentes.append(botao)
        ids_existentes.add(botao.get("id"))

    return relatorio


def eh_botao_automatico(filtro):
    return str(filtro.get("origem") or "").strip().lower() == "automatico"


def obter_executor_botao(nome_relatorio, filtro):
    if not eh_botao_automatico(filtro):
        return ""

    executor = str(filtro.get("executor") or "").strip().lower()
    if executor:
        return executor

    return ""


def eh_filtro_opcional_relatorio(relatorio, filtro):
    executor = obter_executor_relatorio(
        relatorio.get("nome", ""),
        relatorio.get("id_relatorio_operacao"),
        relatorio.get("id") or relatorio.get("id_relatorio"),
        relatorio.get("url", ""),
    )
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
