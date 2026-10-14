Backup pontual do trecho critico do extrato salvo em 2026-04-09.

Objetivo:
- preservar o roteamento do relatorio de extrato para modulo dedicado
- preservar o trecho da execucao que força o executor do extrato

Arquivo de origem: services/relatorio_action_service.py

```python
def _normalizar_nome_relatorio(nome_relatorio):
    return " ".join(str(nome_relatorio or "").strip().lower().split())


RELATORIOS_BOTOES = {
    "extratoclientehistorico": [],
}

RELATORIOS_EXECUTORES = {
    "extratoclientehistorico": "extrato_cliente_historico",
    "extrato cliente historico": "extrato_cliente_historico",
    "relatório de extrato de cliente": "extrato_cliente_historico",
    "relatorio de extrato de cliente": "extrato_cliente_historico",
    "extrato saldo devedor presente": "extrato_saldo_devedor_presente",
}

RELATORIOS_EXECUTORES_OPERACAO = {
    7: "extrato_cliente_historico",
}

RELATORIOS_EXECUTORES_RELATORIO = {
    7: "extrato_cliente_historico",
    2: "extrato_saldo_devedor_presente",
}

RELATORIOS_EXECUTORES_URL = {
    "/common/page/3012": "extrato_cliente_historico",
    "/financeiro/contas-receber/relatorios/saldo-devedor": "extrato_saldo_devedor_presente",
}


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

    if id_relatorio in RELATORIOS_EXECUTORES_RELATORIO:
        return RELATORIOS_EXECUTORES_RELATORIO[id_relatorio]

    url_normalizada = str(url_relatorio or "").strip().lower()
    for trecho_url, executor in RELATORIOS_EXECUTORES_URL.items():
        if trecho_url in url_normalizada:
            return executor

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
```

Arquivo de origem: services/automacao_service.py

```python
    url_normalizada = relatorio_url.lower()
    if "/common/page/3012" in url_normalizada or relatorio_config.get("id") == 7:
        executor_relatorio = "extrato_cliente_historico"
    else:
        executor_relatorio = obter_executor_relatorio(
            relatorio_config.get("nome", ""),
            relatorio_config.get("id_relatorio_operacao"),
            relatorio_config.get("id"),
            relatorio_url,
        )
    if not executor_relatorio:
        raise ValueError(
            "Relatorio sem modulo dedicado configurado: "
            f"id={relatorio_config.get('id')} | "
            f"id_relatorio_operacao={relatorio_config.get('id_relatorio_operacao')} | "
            f"nome={relatorio_config.get('nome', '')}"
        )

    _executar_relatorio_dedicado(driver, wait, relatorio_config, executor_relatorio)
```
