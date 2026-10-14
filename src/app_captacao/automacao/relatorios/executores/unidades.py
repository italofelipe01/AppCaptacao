import time

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select


SELECAO_CAMPO = "filter.selecao"
SELECAO_VALOR = "por Empreendimento"
TIPO_RELATORIO_CAMPO = "filter.tpRelatorio"
TIPO_RELATORIO_VALOR = "Consolidado"
GRUPO_EMPRESA_CAMPO = "filter.grupoEmpresa.grupoEmpresaPK.cdGrupoEmpresa"


def executar(driver, wait, relatorio_config, contexto):
    logger = contexto["logger"]
    normalizar_valor = contexto["normalizar_valor"]
    default_report_wait = contexto["default_report_wait"]
    marcar_inicio_download = contexto["marcar_inicio_download"]
    renomear_download = contexto["renomear_download"]

    filtros = relatorio_config.get("filtros", []) or []

    dt_inicio = _obter_filtro_por_campo(filtros, "filter.dtInicioStr")
    dt_fim = _obter_filtro_por_campo(filtros, "filter.dtFimStr")
    grupo_empresa = _obter_filtro_por_campo(
        filtros,
        GRUPO_EMPRESA_CAMPO,
        "cdGrupoEmpresa",
        "grupoEmpresaPK.cdGrupoEmpresa",
    )
    empresa = _obter_filtro_por_campo(filtros, "cdEmpresaView", "filter.empresa.cdEmpresaView")
    empreendimento = _obter_filtro_por_campo(
        filtros,
        "cdEmpreendView",
        "filter.empreend.cdEmpreendView",
    )

    logger.info("Executor unidades aplicando selects padrao do backend.")
    _selecionar_select(driver, wait, SELECAO_CAMPO, SELECAO_VALOR, logger)
    _selecionar_select(driver, wait, TIPO_RELATORIO_CAMPO, TIPO_RELATORIO_VALOR, logger, obrigatorio=False)
    _aguardar_campos_dependentes(
        driver,
        wait,
        (
            GRUPO_EMPRESA_CAMPO,
            "cdGrupoEmpresa",
            "cdEmpresaView",
            "filter.empresa.cdEmpresaView",
            "cdEmpreendView",
            "filter.empreend.cdEmpreendView",
        ),
        logger,
    )

    if dt_inicio:
        _preencher_campo(
            driver,
            wait,
            _identificadores_data(dt_inicio, "filter.dtInicioStr"),
            normalizar_valor(dt_inicio),
            logger,
        )

    if dt_fim:
        _preencher_campo(
            driver,
            wait,
            _identificadores_data(dt_fim, "filter.dtFimStr"),
            normalizar_valor(dt_fim),
            logger,
        )

    grupos_empresa = _extrair_valores(grupo_empresa)
    empresas = _extrair_valores(empresa)
    empreendimentos = _extrair_valores(empreendimento)
    total = _calcular_total_iteracoes(grupos_empresa, empresas, empreendimentos)

    logger.info("Executor unidades iniciando com %s iteracao(oes).", total)

    for index in range(total):
        if grupo_empresa:
            _preencher_campo(
                driver,
                wait,
                _identificadores_lookup(
                    grupo_empresa,
                    "cdGrupoEmpresa",
                    GRUPO_EMPRESA_CAMPO,
                ),
                _obter_valor_iteracao(grupos_empresa, index),
                logger,
            )

        if empresa:
            _preencher_campo(
                driver,
                wait,
                _identificadores_lookup(empresa, "cdEmpresaView", "filter.empresa.cdEmpresaView"),
                _obter_valor_iteracao(empresas, index),
                logger,
            )

        if empreendimento:
            _preencher_campo(
                driver,
                wait,
                _identificadores_lookup(
                    empreendimento,
                    "cdEmpreendView",
                    "filter.empreend.cdEmpreendView",
                ),
                _obter_valor_iteracao(empreendimentos, index),
                logger,
            )

        logger.info("Executor unidades disparando ENTER na iteracao %s/%s.", index + 1, total)
        inicio_download = marcar_inicio_download()
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(default_report_wait)
        _fechar_janelas_extras(driver)
        renomear_download(relatorio_config, _obter_valor_iteracao(empresas, index), inicio_download)


def _obter_filtro_por_campo(filtros, *campos_identificadores):
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


def _identificadores_data(filtro, campo_padrao):
    return _montar_identificadores(filtro, campo_padrao)


def _identificadores_lookup(filtro, campo_curto, campo_completo):
    return _montar_identificadores(filtro, campo_curto, campo_completo)


def _montar_identificadores(filtro, *fallbacks):
    identificadores = []
    campo_filtro = str(filtro.get("campo_identificador") or "").strip()
    if campo_filtro:
        identificadores.append(campo_filtro)

    for fallback in fallbacks:
        fallback = str(fallback or "").strip()
        if fallback and fallback not in identificadores:
            identificadores.append(fallback)

    return identificadores


def _selecionar_select(driver, wait, identificador, valor, logger, obrigatorio=True):
    try:
        elemento = _localizar_no_primeiro_iframe(driver, wait, identificador)
    except (NoSuchElementException, TimeoutException):
        if obrigatorio:
            raise
        logger.info("Select opcional %s nao encontrado; seguindo fluxo.", identificador)
        driver.switch_to.default_content()
        return

    select = Select(elemento)

    try:
        if identificador == SELECAO_CAMPO and len(select.options) >= 2:
            select.select_by_index(1)
        else:
            select.select_by_value(valor)
    except NoSuchElementException:
        try:
            select.select_by_visible_text(valor)
        except NoSuchElementException:
            if _selecionar_opcao_por_texto_normalizado(select, valor):
                pass
            elif identificador == SELECAO_CAMPO and len(select.options) >= 2:
                select.select_by_index(1)
            else:
                raise
    except Exception:
        driver.execute_script(
            """
            const select = arguments[0];
            const value = arguments[1];
            select.value = value;
            select.dispatchEvent(new Event('input', { bubbles: true }));
            select.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            elemento,
            valor,
        )

    _disparar_eventos_select(driver, elemento)
    logger.info("Select %s definido como %s.", identificador, valor)
    driver.switch_to.default_content()
    time.sleep(1.5)


def _disparar_eventos_select(driver, elemento):
    driver.execute_script(
        """
        const select = arguments[0];
        select.dispatchEvent(new Event('input', { bubbles: true }));
        select.dispatchEvent(new Event('change', { bubbles: true }));
        if (typeof window.verificaSelecao === 'function') {
            window.verificaSelecao();
        }
        """,
        elemento,
    )


def _aguardar_campos_dependentes(driver, wait, identificadores, logger):
    ultimo_erro = None
    for identificador in identificadores:
        try:
            _localizar_no_primeiro_iframe(driver, wait, identificador)
            logger.info("Campo dependente %s ficou disponivel apos a selecao padrao.", identificador)
            driver.switch_to.default_content()
            return
        except (NoSuchElementException, TimeoutException) as exc:
            ultimo_erro = exc
            driver.switch_to.default_content()

    if ultimo_erro:
        logger.warning(
            "Os campos dependentes do relatorio de unidades nao ficaram disponiveis apos a selecao padrao."
        )


def _selecionar_opcao_por_texto_normalizado(select, valor):
    valor_normalizado = _normalizar_texto(valor)

    for indice, option in enumerate(select.options):
        if _normalizar_texto(option.text) == valor_normalizado:
            select.select_by_index(indice)
            return True

    return False


def _preencher_campo(driver, wait, identificadores, valor, logger):
    elemento = _localizar_primeiro_disponivel(driver, wait, identificadores)
    valor_texto = str(valor or "")
    identificador = elemento.get_attribute("id") or elemento.get_attribute("name") or identificadores[0]

    logger.info("Executor unidades preenchendo campo %s com valor %s.", identificador, valor_texto)

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
    if not filtro:
        return []

    valor = filtro.get("valor")
    if isinstance(valor, list):
        return [str(item).strip() for item in valor if str(item).strip()]

    return [parte.strip() for parte in str(valor or "").split(",") if parte.strip()]


def _calcular_total_iteracoes(*listas_valores):
    totais = [len(valores) for valores in listas_valores if valores]
    if not totais:
        return 1

    if len(set(total for total in totais if total > 1)) > 1:
        raise ValueError(
            "Os filtros Empresa e Empreendimento do relatorio de unidades possuem "
            "quantidades de valores diferentes."
        )

    return max(totais)


def _obter_valor_iteracao(valores, index):
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
