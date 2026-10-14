import time

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select


CAMPO_AGRUPAR = "analise.agrupar"
VALOR_AGRUPAR = "Centro de custo"
CAMPO_TIPO_ANALISE = "tipoAnaliseRealizado"
CAMPO_DT_CORRECAO_ATE = "analise.dtCorrecaoAte"
CAMPO_EMPRESA = "analise.empresa.cdEmpresaView"
CAMPO_PERIODO_INICIO = "analise.periodoInicio"
CAMPO_PERIODO_FIM = "analise.periodoFim"
CAMPO_CENTRO_CUSTO = "cdEmpreendView"


def executar(driver, wait, relatorio_config, contexto):
    logger = contexto["logger"]
    normalizar_valor = contexto["normalizar_valor"]
    default_report_wait = contexto["default_report_wait"]
    marcar_inicio_download = contexto["marcar_inicio_download"]
    renomear_download = contexto["renomear_download"]

    filtros = relatorio_config.get("filtros", []) or []

    empresa = _obter_filtro_por_campo(filtros, CAMPO_EMPRESA, "cdEmpresaView")
    periodo_inicio = _obter_filtro_por_campo(filtros, CAMPO_PERIODO_INICIO)
    periodo_fim = _obter_filtro_por_campo(filtros, CAMPO_PERIODO_FIM)
    centro_custo = _obter_filtro_por_campo(filtros, CAMPO_CENTRO_CUSTO)

    logger.info("Executor analitico_propriedade aplicando agrupar antes de qualquer filtro.")
    _selecionar_select(driver, wait, CAMPO_AGRUPAR, VALOR_AGRUPAR, logger)
    _marcar_radio(driver, wait, CAMPO_TIPO_ANALISE, logger)

    empresas = _extrair_valores(empresa)
    centros_custo = _extrair_valores(centro_custo)
    total = _calcular_total_iteracoes(empresas, centros_custo)

    logger.info("Executor analitico_propriedade iniciando com %s iteracao(oes).", total)

    for index in range(total):
        if empresa:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(empresa, CAMPO_EMPRESA, "cdEmpresaView"),
                _obter_valor_iteracao(empresas, index),
                logger,
            )

        if centro_custo:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(centro_custo, CAMPO_CENTRO_CUSTO),
                _obter_valor_iteracao(centros_custo, index),
                logger,
            )

        if periodo_inicio:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(periodo_inicio, CAMPO_PERIODO_INICIO),
                normalizar_valor(periodo_inicio),
                logger,
            )

        if periodo_fim:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(periodo_fim, CAMPO_PERIODO_FIM),
                normalizar_valor(periodo_fim),
                logger,
            )

        logger.info(
            "Executor analitico_propriedade clicando em Visualizar apos periodo fim na iteracao %s/%s.",
            index + 1,
            total,
        )
        inicio_download = marcar_inicio_download()
        _clicar_botao_visualizar(driver, wait, logger)
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


def _selecionar_select(driver, wait, identificador, valor, logger):
    elemento = _localizar_no_primeiro_iframe(driver, wait, identificador)

    try:
        try:
            elemento.click()
            time.sleep(0.5)
        except Exception:
            pass

        try:
            Select(elemento).select_by_value(valor)
        except NoSuchElementException:
            Select(elemento).select_by_visible_text(valor)
        except Exception:
            driver.execute_script(
                """
                const select = arguments[0];
                const value = arguments[1];
                const target = Array.from(select.options).find(
                    (option) => option.value === value || option.text.trim() === value
                );
                if (target) {
                    select.value = target.value;
                } else {
                    select.value = value;
                }
                select.dispatchEvent(new Event('input', { bubbles: true }));
                select.dispatchEvent(new Event('change', { bubbles: true }));
                """,
                elemento,
                valor,
            )

        valor_final = (elemento.get_attribute("value") or "").strip()
        if valor_final.lower() != valor.lower():
            driver.execute_script(
                """
                const select = arguments[0];
                const texto = arguments[1];
                const option = Array.from(select.options).find(
                    (item) => item.text.trim() === texto
                );
                if (!option) {
                    throw new Error(`Opcao nao encontrada: ${texto}`);
                }
                select.value = option.value;
                option.selected = true;
                select.dispatchEvent(new Event('input', { bubbles: true }));
                select.dispatchEvent(new Event('change', { bubbles: true }));
                """,
                elemento,
                valor,
            )
    finally:
        logger.info("Select %s definido como %s.", identificador, valor)
        driver.switch_to.default_content()
        time.sleep(1)


def _marcar_radio(driver, wait, identificador, logger):
    elemento = _localizar_no_primeiro_iframe(driver, wait, identificador)

    try:
        if not elemento.is_selected():
            elemento.click()
            time.sleep(0.5)
    except Exception:
        driver.execute_script(
            """
            const radio = arguments[0];
            if (!radio.checked) {
                radio.checked = true;
                radio.dispatchEvent(new Event('input', { bubbles: true }));
                radio.dispatchEvent(new Event('change', { bubbles: true }));
                radio.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            }
            """,
            elemento,
        )

    logger.info("Radio %s marcado como padrao do backend.", identificador)
    driver.switch_to.default_content()
    time.sleep(1)


def _preencher_campo(driver, wait, identificadores, valor, logger):
    elemento = _localizar_primeiro_disponivel(driver, wait, identificadores)
    valor_texto = str(valor or "")
    identificador = elemento.get_attribute("id") or elemento.get_attribute("name") or identificadores[0]

    logger.info(
        "Executor analitico_propriedade preenchendo campo %s com valor %s.",
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


def _calcular_total_iteracoes(empresas, centros_custo):
    totais = [len(valores) for valores in (empresas, centros_custo) if valores]
    if not totais:
        return 1

    if len(set(total for total in totais if total > 1)) > 1:
        raise ValueError(
            "Os filtros Empresa e Centro de custo do relatorio de analitico de propriedade "
            "possuem quantidades de valores diferentes."
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


def _clicar_botao_visualizar(driver, wait, logger):
    driver.switch_to.default_content()
    iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
    driver.switch_to.frame(iframe)

    try:
        botao = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//input[@type='submit' and (@value='Visualizar' or @class='spwBotaoDefault')]",
                )
            )
        )
        botao.click()
        logger.info("Botao 'Visualizar' clicado com sucesso.")
    finally:
        driver.switch_to.default_content()


def _normalizar_texto(valor):
    return str(valor or "").strip().lower()
