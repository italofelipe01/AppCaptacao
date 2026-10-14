"""Orquestracao de uma execucao: navegador, login, executor dedicado e resultado.

Um relatorio ou uma operacao (varios relatorios) rodam na mesma sessao
autenticada. Cada relatorio termina como baixado, nao_baixado ou ignorado.
"""

from __future__ import annotations

import logging
import time

from selenium.webdriver.support.ui import WebDriverWait

from app_captacao.automacao import campos, downloads, erros, login, navegador
from app_captacao.automacao import relatorios as relatorios_dedicados
from app_captacao.automacao.config import (
    BY_MAP,
    CAMPO_EMPREENDIMENTO,
    CAMPO_EMPRESA,
    DEFAULT_REPORT_WAIT,
    DEFAULT_TIMEOUT,
    DOWNLOAD_DIR,
    KEEP_BROWSER_OPEN,
    POST_LOGIN_WAIT,
)
from app_captacao.catalogo import regras

logger = logging.getLogger(__name__)


def executar_relatorio(email, senha, relatorio_config, driver=None, sessao_autenticada=False):
    driver_gerenciado = driver is None

    try:
        driver = driver or navegador.criar_driver()
        wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
        if not sessao_autenticada:
            login.fazer_login(driver, wait, email, senha)
            time.sleep(POST_LOGIN_WAIT)

        arquivos = _executar_relatorio_no_driver(driver, wait, relatorio_config)
        stable = downloads.aguardar_pasta_download_estabilizar()
        if not stable:
            logger.warning(
                "A pasta de downloads nao estabilizou apos a execucao do relatorio %s. Aguardando mais %s segundos.",
                relatorio_config.get("id"),
                DEFAULT_REPORT_WAIT,
            )
            time.sleep(DEFAULT_REPORT_WAIT)
            downloads.aguardar_pasta_download_estabilizar()
        item = _montar_item_resultado(relatorio_config, "baixado", arquivos=arquivos)
        return {
            "tipo_execucao": "relatorio",
            "itens": [item],
            "sucessos": [item],
            "falhas": [],
            "quantidade_relatorios": 1,
            "quantidade_baixados": 1,
            "quantidade_nao_baixados": 0,
            "resumo": "1 relatorio baixado; 0 nao baixados.",
        }
    except Exception as exc:
        logger.exception("Falha ao executar o relatorio %s.", relatorio_config.get("nome", ""))
        item = _montar_item_resultado(
            relatorio_config,
            "nao_baixado",
            mensagem=erros.mensagem_erro_usuario(exc),
            etapa=getattr(exc, "etapa", "execucao"),
        )
        return {
            "tipo_execucao": "relatorio",
            "itens": [item],
            "sucessos": [],
            "falhas": [item],
            "quantidade_relatorios": 1,
            "quantidade_baixados": 0,
            "quantidade_nao_baixados": 1,
            "mensagem": item["mensagem"],
            "resumo": "0 relatorios baixados; 1 nao baixado.",
        }
    finally:
        if driver_gerenciado and driver and not KEEP_BROWSER_OPEN:
            driver.quit()


def executar_relatorios_em_sequencia(email, senha, relatorios_config, on_report_event=None):
    if not relatorios_config:
        return {
            "quantidade_relatorios": 0,
            "quantidade_baixados": 0,
            "quantidade_nao_baixados": 0,
            "itens": [],
            "sucessos": [],
            "falhas": [],
            "resumo": "Nenhum relatorio para executar.",
        }

    driver = None
    resultado_execucao = {
        "quantidade_relatorios": len(relatorios_config),
        "quantidade_baixados": 0,
        "quantidade_nao_baixados": 0,
        "itens": [],
        "sucessos": [],
        "falhas": [],
    }
    try:
        try:
            driver = navegador.criar_driver()
            wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
            login.fazer_login(driver, wait, email, senha)
        except Exception as exc:
            logger.exception("O navegador ou a autenticacao nao foi concluido; os relatorios serao ignorados.")
            for relatorio_config in relatorios_config:
                item = _montar_item_resultado(
                    relatorio_config,
                    "ignorado",
                    mensagem=(
                        "Navegador ou autenticacao nao concluido: "
                        f"{erros.mensagem_erro_usuario(exc, 'nao foi possivel iniciar a sessao.')}"
                    ),
                    etapa="autenticacao",
                )
                resultado_execucao["itens"].append(item)
                resultado_execucao["falhas"].append(item)
            resultado_execucao["quantidade_nao_baixados"] = len(relatorios_config)
            resultado_execucao["resumo"] = (
                f"0 relatorios baixados; {len(relatorios_config)} nao baixados."
            )
            return resultado_execucao
        time.sleep(POST_LOGIN_WAIT)

        total = len(relatorios_config)
        for indice, relatorio_config in enumerate(relatorios_config, start=1):
            logger.info(
                "Executando relatorio %s/%s na mesma sessao | id=%s | nome=%s",
                indice,
                total,
                relatorio_config.get("id"),
                relatorio_config.get("nome", ""),
            )
            try:
                if on_report_event:
                    on_report_event(
                        "processando",
                        relatorio_config,
                        {
                            "indice": indice,
                            "total": total,
                        },
                    )
                arquivos = _executar_relatorio_no_driver(driver, wait, relatorio_config)
                eh_ultimo = indice == total
                item = _montar_item_resultado(
                    relatorio_config,
                    "baixado",
                    arquivos=arquivos,
                    indice=indice,
                    total=total,
                )
                item["eh_ultimo"] = eh_ultimo
                resultado_execucao["itens"].append(item)
                resultado_execucao["sucessos"].append(item)
                if on_report_event:
                    on_report_event(
                        "sucesso",
                        relatorio_config,
                        {
                            "indice": indice,
                            "total": total,
                            "eh_ultimo": eh_ultimo,
                            "arquivos": arquivos,
                            "caminho_final": arquivos[-1] if arquivos else "",
                        },
                    )
                if not eh_ultimo:
                    stable = downloads.aguardar_pasta_download_estabilizar()
                    if not stable:
                        logger.warning(
                            "A pasta de downloads nao estabilizou apos o relatorio %s. Aguardando mais %s segundos.",
                            relatorio_config.get("id"),
                            DEFAULT_REPORT_WAIT,
                        )
                        time.sleep(DEFAULT_REPORT_WAIT)
                        downloads.aguardar_pasta_download_estabilizar()
                    logger.info(
                        "Aguardando %s segundos antes de iniciar o proximo relatorio.",
                        DEFAULT_REPORT_WAIT,
                    )
                    time.sleep(DEFAULT_REPORT_WAIT)
                else:
                    logger.info("Ultimo relatorio da sequencia. Nao aguarda finalizacao.")
            except Exception as exc:
                detalhe_erro = _montar_item_resultado(
                    relatorio_config,
                    "nao_baixado",
                    mensagem=erros.mensagem_erro_usuario(
                        exc,
                        "Erro na execucao da automacao para o relatorio.",
                    ),
                    etapa=getattr(exc, "etapa", "execucao"),
                    indice=indice,
                    total=total,
                )
                resultado_execucao["itens"].append(detalhe_erro)
                resultado_execucao["falhas"].append(detalhe_erro)
                logger.exception(
                    "Erro na execucao da automacao da operacao para o relatorio %s.",
                    relatorio_config.get("id"),
                )
                if on_report_event:
                    on_report_event("erro", relatorio_config, detalhe_erro)
                if indice < total and not downloads.aguardar_pasta_download_estabilizar():
                    logger.error(
                        "A pasta de downloads permaneceu instavel; os relatorios restantes serao ignorados para evitar associacao incorreta de arquivo."
                    )
                    for indice_restante, relatorio_restante in enumerate(
                        relatorios_config[indice:],
                        start=indice + 1,
                    ):
                        item_ignorado = _montar_item_resultado(
                            relatorio_restante,
                            "ignorado",
                            mensagem="A pasta de downloads nao estabilizou apos a falha anterior.",
                            etapa="download",
                            indice=indice_restante,
                            total=total,
                        )
                        resultado_execucao["itens"].append(item_ignorado)
                        resultado_execucao["falhas"].append(item_ignorado)
                        if on_report_event:
                            on_report_event("erro", relatorio_restante, item_ignorado)
                    break
    finally:
        if driver and not KEEP_BROWSER_OPEN:
            driver.quit()
    resultado_execucao["quantidade_baixados"] = len(resultado_execucao["sucessos"])
    resultado_execucao["quantidade_nao_baixados"] = len(resultado_execucao["falhas"])
    resultado_execucao["resumo"] = (
        f"{resultado_execucao['quantidade_baixados']} relatorio(s) baixado(s); "
        f"{resultado_execucao['quantidade_nao_baixados']} nao baixado(s)."
    )
    return resultado_execucao


def _montar_item_resultado(
    relatorio_config,
    estado,
    arquivos=None,
    mensagem="",
    etapa="",
    indice=None,
    total=None,
):
    arquivos = [str(item) for item in (arquivos or []) if str(item or "").strip()]
    return {
        "indice": indice,
        "total": total,
        "relatorio_id": relatorio_config.get("id") or relatorio_config.get("id_relatorio"),
        "relatorio_nome": relatorio_config.get("nome", ""),
        "operacao_nome": relatorio_config.get("operacao_nome", ""),
        "estado": estado,
        "mensagem": mensagem,
        "etapa": etapa,
        "caminho_final": arquivos[-1] if arquivos else "",
        "arquivos": arquivos,
    }


def _executar_relatorio_no_driver(driver, wait, relatorio_config):
    relatorio_config["_arquivos_finais"] = []
    relatorio_url = (relatorio_config.get("url") or "").strip()
    if not relatorio_url:
        raise ValueError(
            f"O relatorio '{relatorio_config.get('nome', '')}' nao possui UrlRelatorio cadastrada."
        )

    driver.switch_to.default_content()
    navegador.fechar_janelas_extras(driver)

    logger.info(
        "Abrindo relatorio '%s' na URL %s",
        relatorio_config.get("nome", ""),
        relatorio_url,
    )
    driver.get(relatorio_url)
    navegador.aguardar_carregamento_da_pagina(driver, wait)

    url_normalizada = relatorio_url.lower()
    if "/common/page/3012" in url_normalizada or relatorio_config.get("id") == 7:
        executor_relatorio = "extrato_cliente_historico"
    else:
        executor_relatorio = regras.obter_executor_relatorio(
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

    if executor_relatorio != "extrato_saldo_devedor_presente":
        time.sleep(6)

    _executar_relatorio_dedicado(driver, wait, relatorio_config, executor_relatorio)
    navegador.aguardar_carregamento_da_pagina(driver, wait)
    arquivos = list(dict.fromkeys(relatorio_config.get("_arquivos_finais", [])))
    if not arquivos:
        raise erros.DownloadProcessingError(
            "download",
            "O executor terminou, mas nenhum arquivo novo foi confirmado no destino.",
        )
    return arquivos


def _executar_relatorio_dedicado(driver, wait, relatorio_config, executor_relatorio):
    logger.info(
        "Executando relatorio '%s' com executor dedicado '%s'.",
        relatorio_config.get("nome", ""),
        executor_relatorio,
    )
    relatorios_dedicados.executar_relatorio_dedicado(
        executor_relatorio,
        driver,
        wait,
        relatorio_config,
        {
            "logger": logger,
            "by_map": BY_MAP,
            "default_report_wait": DEFAULT_REPORT_WAIT,
            "campo_empresa": CAMPO_EMPRESA,
            "campo_empreendimento": CAMPO_EMPREENDIMENTO,
            "normalizar_valor": campos.normalizar_valor_automacao,
            "preencher_campo_antigo": campos.preencher_campo_legado,
            "preencher_autocomplete_enter": campos.preencher_autocomplete_com_enter,
            "marcar_inicio_download": downloads.marcar_inicio_download,
            "renomear_download": downloads.renomear_download_relatorio,
            "download_dir": DOWNLOAD_DIR,
            "sanitizar_nome_arquivo": downloads.sanitizar_nome_arquivo,
            "copiar_download_para_sharepoint": downloads.copiar_download_para_sharepoint,
            "montar_caminho_download_unico": downloads.montar_caminho_download_unico,
            "capture_debug_snapshot": lambda nome, driver_ref=driver: downloads.capture_debug_snapshot(driver_ref, nome),
        },
    )
