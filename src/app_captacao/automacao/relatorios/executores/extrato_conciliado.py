"""
Módulo de geração do relatório "Extrato Conciliado".

Automatiza a execução do relatório de extrato conciliado via interface web.
Filtros suportados: empresa, data início e data fim.

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
from app_captacao.automacao.navegador import fechar_janelas_extras as _fechar_janelas_extras


# Constantes de identificação dos campos
CAMPO_EMPRESA = "entity.contaCorrente.empresa.cdEmpresaView"
CAMPO_DT_INICIO = "dtInicio"
CAMPO_DT_FIM = "dtFim"


def executar(driver, wait, relatorio_config, contexto):
    """
    Função principal de execução do relatório Extrato Conciliado.
    
    Args:
        driver: Instância do WebDriver do Selenium.
        wait: Instância de WebDriverWait.
        relatorio_config: Configuração do relatório.
        contexto: Dicionário com utilitários.
    """
    logger = contexto["logger"]
    normalizar_valor = contexto["normalizar_valor"]
    default_report_wait = contexto["default_report_wait"]
    marcar_inicio_download = contexto["marcar_inicio_download"]
    renomear_download = contexto["renomear_download"]

    filtros = relatorio_config.get("filtros", []) or []

    empresa = _obter_filtro_por_campo(filtros, CAMPO_EMPRESA, "cdEmpresaView")
    dt_inicio = _obter_filtro_por_campo(filtros, CAMPO_DT_INICIO)
    dt_fim = _obter_filtro_por_campo(filtros, CAMPO_DT_FIM)

    # Preenche campos de período
    if dt_inicio:
        _preencher_campo(
            driver,
            wait,
            _montar_identificadores(dt_inicio, CAMPO_DT_INICIO),
            normalizar_valor(dt_inicio),
            logger,
        )

    if dt_fim:
        _preencher_campo(
            driver,
            wait,
            _montar_identificadores(dt_fim, CAMPO_DT_FIM),
            normalizar_valor(dt_fim),
            logger,
        )

    empresas = _extrair_valores(empresa)
    total = max(len(empresas), 1)

    logger.info("Executor extrato_conciliado iniciando com %s iteracao(oes).", total)

    # Loop de iteração por empresas
    for index in range(total):
        if empresa:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(empresa, CAMPO_EMPRESA, "cdEmpresaView"),
                empresas[index] if index < len(empresas) else "",
                logger,
            )

        logger.info(
            "Executor extrato_conciliado disparando ENTER na iteracao %s/%s.",
            index + 1,
            total,
        )
        inicio_download = marcar_inicio_download()
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(default_report_wait)
        _fechar_janelas_extras(driver)
        renomear_download(relatorio_config, empresas[index] if index < len(empresas) else "", inicio_download)


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
    """Preenche campo de formulário."""
    elemento = _localizar_primeiro_disponivel(driver, wait, identificadores)
    valor_texto = str(valor or "")
    identificador = elemento.get_attribute("id") or elemento.get_attribute("name") or identificadores[0]

    logger.info(
        "Executor extrato_conciliado preenchendo campo %s com valor %s.",
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


def _normalizar_texto(valor):
    """Normaliza texto para comparação case-insensitive."""
    return str(valor or "").strip().lower()
