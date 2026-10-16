"""Orquestracao de uma execucao: navegador, login, executor dedicado e resultado.

Um relatorio ou uma operacao (varios relatorios) rodam na mesma sessao
autenticada. Cada relatorio termina como baixado, nao_baixado ou ignorado.
Se a sessao do Selenium cair no meio da operacao, a automacao se reconecta ao
Edge e refaz o login antes do proximo relatorio.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from selenium.webdriver.support.ui import WebDriverWait

from app_captacao.automacao import campos, downloads, erros, login, navegador
from app_captacao.automacao import relatorios as relatorios_dedicados
from app_captacao.automacao.config import (
    DEFAULT_REPORT_WAIT,
    DEFAULT_TIMEOUT,
    DOWNLOAD_DIR,
    KEEP_BROWSER_OPEN,
    POST_LOGIN_WAIT,
)
from app_captacao.catalogo import regras

logger = logging.getLogger(__name__)

# Quantas vezes uma operacao reabre a sessao do navegador antes de desistir.
MAX_RECONEXOES = 2


def executar_relatorio(email, senha, relatorio_config, driver=None, sessao_autenticada=False, on_report_event=None):
    driver_gerenciado = driver is None

    try:
        try:
            if driver is None:
                driver, wait = _abrir_sessao(email, senha)
            else:
                wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
                if not sessao_autenticada:
                    login.fazer_login(driver, wait, email, senha)
                    navegador.definir_janela_principal(driver)
            if not sessao_autenticada:
                time.sleep(POST_LOGIN_WAIT)
        except Exception as exc:
            # Mesmo criterio da operacao: sem sessao, o relatorio nem foi tentado.
            logger.exception("O navegador ou a autenticacao nao foi concluido; o relatorio sera ignorado.")
            item = _item_ignorado_por_autenticacao(relatorio_config, exc)
            return _resultado_final("relatorio", [item])

        try:
            arquivos = _executar_relatorio_no_driver(driver, wait, relatorio_config, on_report_event)
        except Exception as exc:
            logger.exception("Falha ao executar o relatorio %s.", relatorio_config.get("nome", ""))
            item = _item_de_falha(relatorio_config, exc)
            return _resultado_final("relatorio", [item])

        _aguardar_pasta_entre_relatorios(relatorio_config)
        item = _montar_item_resultado(relatorio_config, "baixado", arquivos=arquivos)
        return _resultado_final("relatorio", [item])
    finally:
        if driver_gerenciado and driver and not KEEP_BROWSER_OPEN:
            _encerrar_driver(driver)


def executar_relatorios_em_sequencia(email, senha, relatorios_config, on_report_event=None):
    if not relatorios_config:
        return _resultado_final("operacao", [], resumo="Nenhum relatorio para executar.")

    driver = None
    itens: list[dict] = []
    total = len(relatorios_config)
    try:
        try:
            driver, wait = _abrir_sessao(email, senha)
        except Exception as exc:
            logger.exception("O navegador ou a autenticacao nao foi concluido; os relatorios serao ignorados.")
            itens = [_item_ignorado_por_autenticacao(relatorio, exc) for relatorio in relatorios_config]
            return _resultado_final("operacao", itens)
        time.sleep(POST_LOGIN_WAIT)

        reconexoes = 0
        for indice, relatorio_config in enumerate(relatorios_config, start=1):
            if not navegador.sessao_do_driver_ativa(driver):
                if reconexoes >= MAX_RECONEXOES:
                    logger.error("A sessao do navegador caiu de novo; os relatorios restantes serao ignorados.")
                    itens += _ignorar_restantes(
                        relatorios_config, indice, total, on_report_event,
                        "A sessao do navegador caiu varias vezes; o relatorio nao foi executado.", "autenticacao",
                    )
                    break
                reconexoes += 1
                logger.warning(
                    "A sessao do navegador caiu; reconectando ao Edge e refazendo o login (%s/%s).",
                    reconexoes,
                    MAX_RECONEXOES,
                )
                _encerrar_driver(driver, fechar_navegador=False)
                driver = None
                try:
                    driver, wait = _abrir_sessao(email, senha)
                    time.sleep(POST_LOGIN_WAIT)
                except Exception:
                    logger.exception("Nao foi possivel reabrir a sessao do navegador.")
                    itens += _ignorar_restantes(
                        relatorios_config, indice, total, on_report_event,
                        "A sessao do navegador caiu e nao foi possivel reconectar.", "autenticacao",
                    )
                    break

            logger.info(
                "Executando relatorio %s/%s na mesma sessao | id=%s | nome=%s",
                indice,
                total,
                relatorio_config.get("id"),
                relatorio_config.get("nome", ""),
            )
            if on_report_event:
                on_report_event("processando", relatorio_config, {"indice": indice, "total": total})
            try:
                arquivos = _executar_relatorio_no_driver(driver, wait, relatorio_config, on_report_event)
            except Exception as exc:
                logger.exception(
                    "Erro na execucao da automacao da operacao para o relatorio %s.",
                    relatorio_config.get("id"),
                )
                item = _item_de_falha(relatorio_config, exc, indice, total)
                itens.append(item)
                if on_report_event:
                    on_report_event("erro", relatorio_config, item)
                _restaurar_janela_principal(driver)
                if indice < total and not downloads.aguardar_pasta_download_estabilizar():
                    logger.error(
                        "A pasta de downloads permaneceu instavel; os relatorios restantes serao ignorados para evitar associacao incorreta de arquivo."
                    )
                    itens += _ignorar_restantes(
                        relatorios_config, indice + 1, total, on_report_event,
                        "A pasta de downloads nao estabilizou apos a falha anterior.", "download",
                    )
                    break
                continue

            item = _montar_item_resultado(relatorio_config, "baixado", arquivos=arquivos, indice=indice, total=total)
            item["eh_ultimo"] = indice == total
            itens.append(item)
            if on_report_event:
                on_report_event(
                    "sucesso",
                    relatorio_config,
                    {
                        "indice": indice,
                        "total": total,
                        "eh_ultimo": indice == total,
                        "arquivos": arquivos,
                        "caminho_final": arquivos[-1] if arquivos else "",
                        "mensagem": item["mensagem"],
                    },
                )
            if indice < total:
                _aguardar_pasta_entre_relatorios(relatorio_config)
                logger.info("Aguardando %s segundos antes de iniciar o proximo relatorio.", DEFAULT_REPORT_WAIT)
                time.sleep(DEFAULT_REPORT_WAIT)
    finally:
        if driver and not KEEP_BROWSER_OPEN:
            _encerrar_driver(driver)
    return _resultado_final("operacao", itens)


def _abrir_sessao(email, senha):
    """Cria o driver, faz o login e guarda a aba do Sienge como janela de trabalho."""
    driver = navegador.criar_driver()
    wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
    try:
        login.fazer_login(driver, wait, email, senha)
        navegador.definir_janela_principal(driver)
    except Exception:
        if not KEEP_BROWSER_OPEN:
            _encerrar_driver(driver)
        raise
    return driver, wait


def _restaurar_janela_principal(driver):
    """Depois de uma falha, volta para a aba do Sienge para o proximo relatorio."""
    try:
        navegador.voltar_para_janela_principal(driver)
    except Exception:
        logger.warning("Nao foi possivel voltar para a aba do Sienge depois da falha.", exc_info=True)


def _aguardar_pasta_entre_relatorios(relatorio_config):
    if downloads.aguardar_pasta_download_estabilizar():
        return
    logger.warning(
        "A pasta de downloads nao estabilizou apos o relatorio %s. Aguardando mais %s segundos.",
        relatorio_config.get("id"),
        DEFAULT_REPORT_WAIT,
    )
    time.sleep(DEFAULT_REPORT_WAIT)
    downloads.aguardar_pasta_download_estabilizar()


def _ignorar_restantes(relatorios_config, primeiro_indice, total, on_report_event, mensagem, etapa):
    itens = []
    for indice, relatorio in enumerate(relatorios_config[primeiro_indice - 1:], start=primeiro_indice):
        item = _montar_item_resultado(relatorio, "ignorado", mensagem=mensagem, etapa=etapa, indice=indice, total=total)
        itens.append(item)
        if on_report_event:
            on_report_event("erro", relatorio, item)
    return itens


def _resultado_final(tipo_execucao, itens, resumo=""):
    sucessos = [item for item in itens if item.get("estado") == "baixado"]
    falhas = [item for item in itens if item.get("estado") != "baixado"]
    if not resumo:
        resumo = f"{len(sucessos)} relatório(s) baixado(s); {len(falhas)} não baixado(s)."
        pastas = _pastas_dos_arquivos(arquivo for item in itens for arquivo in item.get("arquivos", []))
        if pastas:
            resumo += f" Arquivos em: {'; '.join(pastas)}."
    resultado = {
        "tipo_execucao": tipo_execucao,
        "itens": itens,
        "sucessos": sucessos,
        "falhas": falhas,
        "quantidade_relatorios": len(itens),
        "quantidade_baixados": len(sucessos),
        "quantidade_nao_baixados": len(falhas),
        "resumo": resumo,
    }
    if tipo_execucao == "relatorio" and falhas:
        resultado["mensagem"] = falhas[0]["mensagem"]
    return resultado


def _pastas_dos_arquivos(arquivos) -> list[str]:
    return list(dict.fromkeys(str(Path(arquivo).parent) for arquivo in arquivos if str(arquivo or "").strip()))


def _descrever_arquivos(arquivos) -> str:
    nomes = [Path(arquivo).name for arquivo in arquivos]
    lista = ", ".join(nomes[:5]) + (f" e mais {len(nomes) - 5}" if len(nomes) > 5 else "")
    return f"{len(nomes)} arquivo(s) salvo(s) em {'; '.join(_pastas_dos_arquivos(arquivos))}: {lista}."


def _encerrar_driver(driver, fechar_navegador=True):
    """Fecha o navegador sem perder o resultado: falha aqui so vai para o log.

    fechar_navegador=False so desconecta: a sessao caiu e o mesmo Edge vai ser reanexado.
    """
    try:
        navegador.encerrar_driver(driver, fechar_edge_anexado=fechar_navegador)
    except Exception:
        logger.warning("Nao foi possivel encerrar o navegador da automacao.", exc_info=True)


def _item_ignorado_por_autenticacao(relatorio_config, exc):
    return _montar_item_resultado(
        relatorio_config,
        "ignorado",
        mensagem=(
            "Navegador ou autenticacao nao concluido: "
            f"{erros.mensagem_erro_usuario(exc, 'nao foi possivel iniciar a sessao.')}"
        ),
        etapa="autenticacao",
    )


def _item_de_falha(relatorio_config, exc, indice=None, total=None):
    """Item nao_baixado; arquivos ja salvos antes da falha (outras empresas) continuam listados."""
    mensagem = erros.mensagem_erro_usuario(exc, "Erro na execucao da automacao para o relatorio.")
    salvos = list(dict.fromkeys(relatorio_config.get("_arquivos_finais", [])))
    if salvos:
        mensagem = f"{mensagem} Antes da falha: {_descrever_arquivos(salvos)}"
    return _montar_item_resultado(
        relatorio_config,
        "nao_baixado",
        arquivos=salvos,
        mensagem=mensagem,
        etapa=getattr(exc, "etapa", "execucao"),
        indice=indice,
        total=total,
    )


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
    if estado == "baixado" and not mensagem and arquivos:
        mensagem = _descrever_arquivos(arquivos)
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


def _aviso_de_arquivo_salvo(relatorio_config, on_report_event):
    """Mostra na tela, durante a execucao, cada arquivo que chegou ao destino."""

    def avisar(caminho_final):
        quantidade = len(relatorio_config.get("_arquivos_finais", []))
        logger.info("Relatorio '%s': arquivo %s salvo em %s", relatorio_config.get("nome", ""), quantidade, caminho_final)
        if on_report_event:
            on_report_event(
                "progresso",
                relatorio_config,
                {"mensagem": f"{quantidade} arquivo(s) salvo(s); ultimo: {caminho_final}"},
            )

    return avisar


def _executar_relatorio_no_driver(driver, wait, relatorio_config, on_report_event=None):
    relatorio_config["_arquivos_finais"] = []
    relatorio_url = (relatorio_config.get("url") or "").strip()
    if not relatorio_url:
        raise ValueError(
            f"O relatorio '{relatorio_config.get('nome', '')}' nao possui UrlRelatorio cadastrada."
        )

    executor_relatorio = regras.executor_do_relatorio(relatorio_config)
    if not executor_relatorio:
        raise ValueError(
            "Relatorio sem modulo dedicado configurado: "
            f"id={relatorio_config.get('id')} | "
            f"nome={relatorio_config.get('nome', '')}"
        )

    navegador.fechar_janelas_extras(driver)

    logger.info(
        "Abrindo relatorio '%s' na URL %s",
        relatorio_config.get("nome", ""),
        relatorio_url,
    )
    driver.get(relatorio_url)
    navegador.aguardar_carregamento_da_pagina(driver, wait)

    if executor_relatorio != "extrato_saldo_devedor_presente":
        time.sleep(6)

    relatorio_config["_ao_registrar_arquivo"] = _aviso_de_arquivo_salvo(relatorio_config, on_report_event)
    try:
        _executar_relatorio_dedicado(driver, wait, relatorio_config, executor_relatorio)
    finally:
        relatorio_config.pop("_ao_registrar_arquivo", None)
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
            "default_report_wait": DEFAULT_REPORT_WAIT,
            "normalizar_valor": campos.normalizar_valor_automacao,
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
