import time

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from app_captacao.automacao.navegador import fechar_janelas_extras as _fechar_janelas_extras


def executar(driver, wait, relatorio_config, contexto):
    logger = contexto["logger"]
    normalizar_valor = contexto["normalizar_valor"]
    default_report_wait = contexto["default_report_wait"]
    marcar_inicio_download = contexto["marcar_inicio_download"]
    renomear_download = contexto["renomear_download"]

    filtros = relatorio_config.get("filtros", []) or []

    empresa = _obter_filtro_por_campo(filtros, "entity.empresa.cdEmpresaView")
    dt_emissao_inicio = _obter_filtro_por_campo(filtros, "dtEmissaoInicio")
    dt_emissao_fim = _obter_filtro_por_campo(filtros, "dtEmissaoFim")

    if dt_emissao_inicio:
        _preencher_campo_legado(
            driver,
            wait,
            "dtEmissaoInicio",
            normalizar_valor(dt_emissao_inicio),
            By.ID,
            logger,
        )

    if dt_emissao_fim:
        _preencher_campo_legado(
            driver,
            wait,
            "dtEmissaoFim",
            normalizar_valor(dt_emissao_fim),
            By.ID,
            logger,
        )

    empresas = _extrair_valores(empresa)
    total = max(len(empresas), 1)

    logger.info("Executor retencao iniciando com %s iteracao(oes).", total)

    index = 0
    while index < total:
        if empresa:
            _preencher_campo_legado(
                driver,
                wait,
                "entity.empresa.cdEmpresaView",
                str(empresas[index]) if index < len(empresas) else "",
                By.ID,
                logger,
            )

        logger.info("Executor retencao disparando ENTER na iteracao %s/%s.", index + 1, total)
        inicio_download = marcar_inicio_download()
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(default_report_wait)
        _fechar_janelas_extras(driver)
        renomear_download(relatorio_config, str(empresas[index]) if index < len(empresas) else "", inicio_download)
        index += 1


def _obter_filtro_por_campo(filtros, campo_identificador):
    campo_normalizado = str(campo_identificador or "").strip().lower()
    for filtro in filtros:
        if str(filtro.get("campo_identificador") or "").strip().lower() == campo_normalizado:
            return filtro
    return None


def _extrair_valores(filtro):
    if not filtro:
        return []

    valor = filtro.get("valor")
    if isinstance(valor, list):
        return [str(item).strip() for item in valor if str(item).strip()]

    return [parte.strip() for parte in str(valor or "").split(",") if parte.strip()]


def _preencher_campo_legado(driver, wait, identificador, valor, by, logger):
    iframe = wait.until(lambda current_driver: current_driver.find_element(By.TAG_NAME, "iframe"))
    driver.switch_to.frame(iframe)

    logger.info(
        "Modulo retencao preenchendo | by=%s | campo=%s | valor=%s",
        by,
        identificador,
        valor,
    )

    try:
        campo = driver.find_element(by, identificador)
        campo.clear()
        time.sleep(1)
        campo.send_keys(str(valor or ""), Keys.TAB)
        time.sleep(1)
    finally:
        driver.switch_to.default_content()
        time.sleep(1)
