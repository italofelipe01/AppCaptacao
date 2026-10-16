"""
Módulo de geração do relatório "Análise de Resultado Sintético".

Este módulo automatiza a execução do relatório de análise de resultados
utilizando Selenium para interação com a interface web. Suporta filtros
por empresa, período, centro de custo e opções de agrupamento.

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
from selenium.webdriver.support.ui import Select
from app_captacao.automacao.navegador import fechar_janelas_extras as _fechar_janelas_extras


# Constantes de identificação dos campos na interface
# Estas constantes definem os identificadores usados para localizar
# os campos do formulário na página web
CAMPO_AGRUPAR = "analise.agrupar"
VALOR_AGRUPAR = "Centro de custo"  # Valor padrão para agrupamento
CAMPO_TIPO_ANALISE = "analise.tipoAnalise"
CAMPO_DT_CORRECAO_ATE = "analise.dtCorrecaoAte"
CAMPO_EMPRESA = "analise.empresa.cdEmpresaView"
CAMPO_PERIODO_INICIO = "analise.periodoInicio"
CAMPO_PERIODO_FIM = "analise.periodoFim"
CAMPO_CENTRO_CUSTO = "cdEmpreendView"


def executar(driver, wait, relatorio_config, contexto):
    """
    Função principal de execução do relatório Análise de Resultado Sintético.
    
    Coordena o processo completo: extração de filtros, preenchimento de campos,
    iteração por empresas/centros de custo e download dos relatórios gerados.
    
    Args:
        driver: Instância do WebDriver do Selenium.
        wait: Instância de WebDriverWait para esperas explícitas.
        relatorio_config: Dicionário com configuração e filtros do relatório.
        contexto: Dicionário com utilitários compartilhados (logger, normalizadores).
    """
    logger = contexto["logger"]
    normalizar_valor = contexto["normalizar_valor"]
    default_report_wait = contexto["default_report_wait"]
    marcar_inicio_download = contexto["marcar_inicio_download"]
    renomear_download = contexto["renomear_download"]

    filtros = relatorio_config.get("filtros", []) or []

    dt_correcao_ate = _obter_filtro_por_campo(filtros, CAMPO_DT_CORRECAO_ATE)
    empresa = _obter_filtro_por_campo(filtros, CAMPO_EMPRESA, "cdEmpresaView")
    periodo_inicio = _obter_filtro_por_campo(filtros, CAMPO_PERIODO_INICIO)
    periodo_fim = _obter_filtro_por_campo(filtros, CAMPO_PERIODO_FIM)
    centro_custo = _obter_filtro_por_campo(filtros, CAMPO_CENTRO_CUSTO)

    # Aplica configurações padrão do backend antes dos filtros do usuário
    # Marca o checkbox de tipo de análise e seleciona opção de agrupamento
    logger.info("Executor analise_resultado_sintetico aplicando campos padrao.")
    _marcar_checkbox(driver, wait, CAMPO_TIPO_ANALISE, logger)
    _selecionar_select(driver, wait, CAMPO_AGRUPAR, VALOR_AGRUPAR, logger)

    # Preenche data de correção se estiver configurada
    if dt_correcao_ate:
        _preencher_campo(
            driver,
            wait,
            _montar_identificadores(dt_correcao_ate, CAMPO_DT_CORRECAO_ATE),
            normalizar_valor(dt_correcao_ate),
            logger,
        )

    empresas = _extrair_valores(empresa)
    centros_custo = _extrair_valores(centro_custo)
    total = _calcular_total_iteracoes(empresas, centros_custo)

    logger.info("Executor analise_resultado_sintetico iniciando com %s iteracao(oes).", total)

    # Loop de iteração por cada combinação de empresa e centro de custo
    # O total de iterações é calculado baseado nas listas de valores
    for index in range(total):
        # Preenche empresa na iteração atual
        if empresa:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(empresa, CAMPO_EMPRESA, "cdEmpresaView"),
                _obter_valor_iteracao(empresas, index),
                logger,
            )

        # Preenche período inicial se configurado
        if periodo_inicio:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(periodo_inicio, CAMPO_PERIODO_INICIO),
                normalizar_valor(periodo_inicio),
                logger,
            )

        # Preenche período final se configurado
        if periodo_fim:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(periodo_fim, CAMPO_PERIODO_FIM),
                normalizar_valor(periodo_fim),
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

        # Dispara geração do relatório e renomeia arquivo baixado
        logger.info(
            "Executor analise_resultado_sintetico disparando ENTER apos centro de custo na iteracao %s/%s.",
            index + 1,
            total,
        )
        inicio_download = marcar_inicio_download()
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(default_report_wait)
        renomear_download(relatorio_config, _obter_valor_iteracao(empresas, index), inicio_download)
        _fechar_janelas_extras(driver)


def _obter_filtro_por_campo(filtros, *campos_identificadores):
    """
    Busca um filtro que corresponda a qualquer um dos identificadores fornecidos.
    
    Suporta múltiplos identificadores como fallback, útil quando o campo pode
    ter variações de nomenclatura entre diferentes versões do sistema.
    
    Args:
        filtros: Lista de dicionários de filtros configurados.
        campos_identificadores: Identificadores alternativos do campo.
    
    Returns:
        Dicionário do primeiro filtro encontrado ou None.
    """
    # Normaliza os identificadores para comparação case-insensitive
    campos_normalizados = {
        _normalizar_texto(campo)
        for campo in campos_identificadores
        if str(campo or "").strip()
    }

    for filtro in filtros:
        campo = _normalizar_texto(filtro.get("campo_identificador"))
        if campo in campos_normalizados:
            return filtro

        # Verifica se o campo termina com algum dos identificadores esperados
        if any(campo.endswith(f".{campo_esperado}") for campo_esperado in campos_normalizados):
            return filtro

    return None


def _montar_identificadores(filtro, *fallbacks):
    """
    Monta lista de identificadores para busca de campo na interface.
    
    Utiliza o identificador do filtro mais fallbacks como alternativas
    para aumentar a chance de encontrar o campo na página.
    
    Args:
        filtro: Dicionário do filtro com campo_identificador.
        fallbacks: Identificadores alternativos a adicionar.
    
    Returns:
        Lista de strings com identificadores prioritizados.
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


def _selecionar_select(driver, wait, identificador, valor, logger):
    """
    Seleciona uma opção em um elemento select (dropdown) da página.
    
    Tenta múltiplas estratégias: primeiro por value, depois por texto visível,
    e por último via JavaScript se as anteriores falharem.
    
    Args:
        driver: Instância do WebDriver.
        wait: Instância de WebDriverWait.
        identificador: ID ou nome do elemento select.
        valor: Valor ou texto da opção a selecionar.
        logger: Instância de logger.
    """
    elemento = _localizar_no_primeiro_iframe(driver, wait, identificador)

    try:
        # Estratégia 1: tentar selecionar por value do option
        Select(elemento).select_by_value(valor)
    except NoSuchElementException:
        # Estratégia 2: tentar selecionar pelo texto visível
        Select(elemento).select_by_visible_text(valor)
    except Exception:
        # Estratégia 3: forçar valor via JavaScript (para casos especiais)
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

    logger.info("Select %s definido como %s.", identificador, valor)
    driver.switch_to.default_content()
    time.sleep(1)


def _marcar_checkbox(driver, wait, identificador, logger):
    """
    Marca um checkbox como marcado (checked).
    
    Utiliza click primário e fallback via JavaScript para garantir que
    o checkbox seja marcado independente do estado atual.
    
    Args:
        driver: Instância do WebDriver.
        wait: Instância de WebDriverWait.
        identificador: ID ou nome do checkbox.
        logger: Instância de logger.
    """
    elemento = _localizar_no_primeiro_iframe(driver, wait, identificador)

    try:
        if not elemento.is_selected():
            elemento.click()
            time.sleep(0.5)
    except Exception:
        # Fallback via JavaScript para casos onde click não funciona
        driver.execute_script(
            """
            const checkbox = arguments[0];
            if (!checkbox.checked) {
                checkbox.checked = true;
                checkbox.dispatchEvent(new Event('input', { bubbles: true }));
                checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                checkbox.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            }
            """,
            elemento,
        )

    logger.info("Checkbox %s marcado como padrao do backend.", identificador)
    driver.switch_to.default_content()
    time.sleep(1)


def _preencher_campo(driver, wait, identificadores, valor, logger):
    elemento = _localizar_primeiro_disponivel(driver, wait, identificadores)
    valor_texto = str(valor or "")
    identificador = elemento.get_attribute("id") or elemento.get_attribute("name") or identificadores[0]

    logger.info(
        "Executor analise_resultado_sintetico preenchendo campo %s com valor %s.",
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
            "Os filtros Empresa e Centro de Custo do relatorio de analise de resultado "
            "sintetico possuem quantidades de valores diferentes."
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


def _normalizar_texto(valor):
    return str(valor or "").strip().lower()
