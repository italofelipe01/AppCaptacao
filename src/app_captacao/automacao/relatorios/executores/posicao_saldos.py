"""
Módulo de geração do relatório "Posição de Saldos".

Suporta filtros por grupo de empresa, empresa e data início.

Autor: Sistema de Automação de Relatórios
Data: 2026
"""
import time

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC


# Constantes de identificação dos campos
CAMPO_GRUPO_EMPRESA = "entity.contaCorrente.empresa.cdGrupoEmpresa"
CAMPO_EMPRESA = "entity.contaCorrente.empresa.cdEmpresaView"
CAMPO_DT_INICIO = "dtInicio"


def executar(driver, wait, relatorio_config, contexto):
    """Função principal de execução do relatório Posição de Saldos."""
    logger = contexto["logger"]
    normalizar_valor = contexto["normalizar_valor"]
    default_report_wait = contexto["default_report_wait"]
    marcar_inicio_download = contexto["marcar_inicio_download"]
    renomear_download = contexto["renomear_download"]

    filtros = relatorio_config.get("filtros", []) or []

    # Extrai filtros específicos do relatório
    grupo_empresa = _obter_filtro_por_campo(filtros, CAMPO_GRUPO_EMPRESA, "cdGrupoEmpresa")
    empresa = _obter_filtro_por_campo(filtros, CAMPO_EMPRESA, "cdEmpresaView")
    dt_inicio = _obter_filtro_por_campo(filtros, CAMPO_DT_INICIO)

    if dt_inicio:
        _preencher_campo(
            driver,
            wait,
            _montar_identificadores(dt_inicio, CAMPO_DT_INICIO),
            normalizar_valor(dt_inicio),
            logger,
        )

    grupos_empresa = _extrair_valores(grupo_empresa)
    empresas = _extrair_valores(empresa)
    total = _calcular_total_iteracoes(grupos_empresa, empresas)

    logger.info("Executor posicao_saldos iniciando com %s iteracao(oes).", total)

    # Loop de iteração processando grupo empresa + empresa
    for index in range(total):
        if grupo_empresa:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(grupo_empresa, CAMPO_GRUPO_EMPRESA, "cdGrupoEmpresa"),
                _obter_valor_iteracao(grupos_empresa, index),
                logger,
            )

        if empresa:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(empresa, CAMPO_EMPRESA, "cdEmpresaView"),
                _obter_valor_iteracao(empresas, index),
                logger,
            )

        logger.info(
            "Executor posicao_saldos disparando ENTER na iteracao %s/%s.",
            index + 1,
            total,
        )
        inicio_download = marcar_inicio_download()
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(default_report_wait)
        _fechar_janelas_extras(driver)
        renomear_download(relatorio_config, _obter_valor_iteracao(empresas, index), inicio_download)


def _obter_filtro_por_campo(filtros, *campos_identificadores):
    """Busca filtro por identificador com fallbacks."""
    campos_normalizados = {
        _normalizar_texto(campo)
        for campo in campos_identificadores
        if str(campo or "").strip()
    }

    for filtro in filtros:
        campo = _normalizar_texto(filtro.get("campo_identificador"))
        if campo in campos_normalizados:
            return filtro
        if any(campo.endswith(f".{campo_esperado}") for campo_esperado in campos_normalizados):
            return filtro

    return None


def _montar_identificadores(filtro, *fallbacks):
    """Monta lista de identificadores para busca de campo."""
    identificadores = []
    campo_filtro = str(filtro.get("campo_identificador") or "").strip()
    if campo_filtro:
        identificadores.append(campo_filtro)

    for fallback in fallbacks:
        fallback = str(fallback or "").strip()
        if fallback and fallback not in identificadores:
            identificadores.append(fallback)

    return identificadores


def _preencher_campo(driver, wait, identificadores, valor, logger):
    """Preenche campo de formulário com valor."""
    elemento = _localizar_primeiro_disponivel(driver, wait, identificadores)
    valor_texto = str(valor or "")
    identificador = elemento.get_attribute("id") or elemento.get_attribute("name") or identificadores[0]

    logger.info(
        "Executor posicao_saldos preenchendo campo %s com valor %s.",
        identificador,
        valor_texto,
    )

    try:
        elemento.click()
        time.sleep(0.5)
        elemento.clear()
        time.sleep(0.5)
        elemento.send_keys(valor_texto, Keys.TAB)
        time.sleep(1)
    finally:
        driver.switch_to.default_content()


def _localizar_primeiro_disponivel(driver, wait, identificadores):
    """Tenta localizar elemento usando múltiplos identificadores."""
    ultimo_erro = None
    for identificador in identificadores:
        try:
            return _localizar_no_primeiro_iframe(driver, wait, identificador)
        except (NoSuchElementException, TimeoutException) as exc:
            ultimo_erro = exc
            driver.switch_to.default_content()

    if ultimo_erro:
        raise ultimo_erro
    raise NoSuchElementException("Nenhum identificador informado para localizar o campo.")


def _localizar_no_primeiro_iframe(driver, wait, identificador):
    """Localiza elemento dentro do primeiro iframe."""
    driver.switch_to.default_content()
    iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
    driver.switch_to.frame(iframe)

    for by in (By.ID, By.NAME):
        try:
            return wait.until(EC.presence_of_element_located((by, identificador)))
        except TimeoutException:
            continue

    raise NoSuchElementException(f"Campo nao localizado: {identificador}")


def _extrair_valores(filtro):
    """Extrai valores de filtro para lista."""
    if not filtro:
        return []
    valor = filtro.get("valor")
    if isinstance(valor, list):
        return [str(item).strip() for item in valor if str(item).strip()]
    return [parte.strip() for parte in str(valor or "").split(",") if parte.strip()]


def _calcular_total_iteracoes(grupos_empresa, empresas):
    """
    Calcula total de iterações validando tamanhos iguais.
    """
    totais = [len(valores) for valores in (grupos_empresa, empresas) if valores]
    if not totais:
        return 1

    if len(set(total for total in totais if total > 1)) > 1:
        raise ValueError(
            "Os filtros Grupo de Empresas e Empresa do relatorio de posicao de saldos "
            "possuem quantidades de valores diferentes."
        )

    return max(totais)


def _obter_valor_iteracao(valores, index):
    """Obtém valor no índice ou repete se único."""
    if not valores:
        return ""
    if index < len(valores):
        return valores[index]
    if len(valores) == 1:
        return valores[0]
    return ""


def _fechar_janelas_extras(driver):
    main_window_handle = driver.current_window_handle
    handles = list(driver.window_handles)

    for handle in handles:
        if handle == main_window_handle:
            continue
        driver.switch_to.window(handle)
        driver.close()

    driver.switch_to.window(main_window_handle)


def _normalizar_texto(valor):
    return str(valor or "").strip().lower()
