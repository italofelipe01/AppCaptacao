"""
Módulo de geração do relatório "Contas Recebidas".

Automatiza a execução do relatório de contas recebidas via interface web.
Suporta filtros por empresa, centro de custo e período de recebimento.

Dependências:
    - selenium: Automação de navegador
    - time: Controle de temporização

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
CAMPO_EMPRESA = "cdEmpresaView"
CAMPO_CENTRO_CUSTO = "cdEmpreendView"
CAMPO_DT_RECEBIMENTO_INICIO = "dtRectoInicio"
CAMPO_DT_RECEBIMENTO_FIM = "dtRectoFim"


def executar(driver, wait, relatorio_config, contexto):
    """
    Função principal de execução do relatório Contas Recebidas.
    
    Args:
        driver: Instância do WebDriver do Selenium.
        wait: Instância de WebDriverWait.
        relatorio_config: Configuração do relatório com filtros.
        contexto: Dicionário com utilitários (logger, normalizadores, etc).
    """
    logger = contexto["logger"]
    normalizar_valor = contexto["normalizar_valor"]
    default_report_wait = contexto["default_report_wait"]
    marcar_inicio_download = contexto["marcar_inicio_download"]
    renomear_download = contexto["renomear_download"]

    filtros = relatorio_config.get("filtros", []) or []

    empresa = _obter_filtro_por_campo(filtros, CAMPO_EMPRESA)
    centro_custo = _obter_filtro_por_campo(filtros, CAMPO_CENTRO_CUSTO)
    dt_inicio = _obter_filtro_por_campo(filtros, CAMPO_DT_RECEBIMENTO_INICIO)
    dt_fim = _obter_filtro_por_campo(filtros, CAMPO_DT_RECEBIMENTO_FIM)

    # Preenche campos de período de recebimento (data início e fim)
    if dt_inicio:
        _preencher_campo(
            driver,
            wait,
            _montar_identificadores(dt_inicio, CAMPO_DT_RECEBIMENTO_INICIO),
            normalizar_valor(dt_inicio),
            logger,
        )

    if dt_fim:
        _preencher_campo(
            driver,
            wait,
            _montar_identificadores(dt_fim, CAMPO_DT_RECEBIMENTO_FIM),
            normalizar_valor(dt_fim),
            logger,
        )

    empresas = _extrair_valores(empresa)
    centros_custo = _extrair_valores(centro_custo)
    total = _calcular_total_iteracoes(empresas, centros_custo)

    logger.info("Executor contas_recebidas iniciando com %s iteracao(oes).", total)

    # Loop de iteração processando cada combinação empresa/centro de custo
    for index in range(total):
        # Preenche empresa na iteração atual
        if empresa:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(empresa, CAMPO_EMPRESA),
                _obter_valor_iteracao(empresas, index),
                logger,
            )

        # Preenche centro de custo na iteração atual
        if centro_custo:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(centro_custo, CAMPO_CENTRO_CUSTO),
                _obter_valor_iteracao(centros_custo, index),
                logger,
            )

        # Dispara geração do relatório
        logger.info(
            "Executor contas_recebidas disparando ENTER na iteracao %s/%s.",
            index + 1,
            total,
        )
        inicio_download = marcar_inicio_download()
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(default_report_wait)
        _fechar_janelas_extras(driver)
        renomear_download(relatorio_config, _obter_valor_iteracao(empresas, index), inicio_download)


def _obter_filtro_por_campo(filtros, *campos_identificadores):
    """
    Busca filtro correspondente a um dos identificadores fornecidos.
    
    Args:
        filtros: Lista de filtros configurados.
        campos_identificadores: Identificadores alternativos do campo.
    
    Returns:
        Filtro encontrado ou None.
    """
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
    """
    Monta lista de identificadores para busca de campo.
    
    Args:
        filtro: Dicionário do filtro.
        fallbacks: Identificadores alternativos.
    
    Returns:
        Lista de identificadores.
    """
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
    """
    Preenche um campo de formulário com o valor fornecido.
    
    Args:
        driver: Instância do WebDriver.
        wait: Instância de WebDriverWait.
        identificadores: Lista de identificadores para localizar o campo.
        valor: Valor a ser inserido.
        logger: Instância de logger.
    """
    elemento = _localizar_primeiro_disponivel(driver, wait, identificadores)
    valor_texto = str(valor or "")
    identificador = elemento.get_attribute("id") or elemento.get_attribute("name") or identificadores[0]

    logger.info(
        "Executor contas_recebidas preenchendo campo %s com valor %s.",
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
    """
    Tenta localizar elemento usando uma lista de identificadores.
    
    Itera pelos identificadores até encontrar o elemento ou lança exceção.
    
    Args:
        driver: Instância do WebDriver.
        wait: Instância de WebDriverWait.
        identificadores: Lista de identificadores a tentar.
    
    Returns:
        Elemento encontrado.
    
    Raises:
        NoSuchElementException: Se nenhum identificador funcionar.
    """
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
    """
    Localiza elemento dentro do primeiro iframe da página.
    
    Args:
        driver: Instância do WebDriver.
        wait: Instância de WebDriverWait.
        identificador: ID ou nome do elemento.
    
    Returns:
        Elemento encontrado.
    """
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
    """
    Extrai valores de um filtro para lista de strings.
    
    Args:
        filtro: Dicionário do filtro.
    
    Returns:
        Lista de valores extraídos.
    """
    if not filtro:
        return []

    valor = filtro.get("valor")
    if isinstance(valor, list):
        return [str(item).strip() for item in valor if str(item).strip()]

    return [parte.strip() for parte in str(valor or "").split(",") if parte.strip()]


def _calcular_total_iteracoes(empresas, centros_custo):
    """
    Calcula o número total de iterações baseado nas listas de valores.
    
    Valida que ambas as listas tenham o mesmo comprimento se ambas
    tiverem mais de um elemento.
    
    Args:
        empresas: Lista de empresas.
        centros_custo: Lista de centros de custo.
    
    Returns:
        Número de iterações.
    
    Raises:
        ValueError: Se as listas tiverem tamanhos diferentes.
    """
    totais = [len(valores) for valores in (empresas, centros_custo) if valores]
    if not totais:
        return 1

    if len(set(total for total in totais if total > 1)) > 1:
        raise ValueError(
            "Os filtros Empresa e Centro de Custo do relatorio de contas recebidas "
            "possuem quantidades de valores diferentes."
        )

    return max(totais)


def _obter_valor_iteracao(valores, index):
    """
    Obtém o valor de uma lista no índice especificado.
    
    Se o índice ultrapassar o comprimento da lista mas a lista tiver
    apenas um elemento, retorna esse único elemento (repetição).
    
    Args:
        valores: Lista de valores.
        index: Índice desejado.
    
    Returns:
        Valor no índice ou string vazia se não disponível.
    """
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
