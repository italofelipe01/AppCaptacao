"""
Módulo de geração do relatório "Preço Total de Vendas".

Suporta filtros por empresa, empreendimento e período.

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
CAMPO_EMPRESA = "filter.empresa.cdEmpresaView"
CAMPO_EMPREENDIMENTO = "filter.empreend.cdEmpreendView"
CAMPO_DT_INICIO = "filter.dtInicioStr"
CAMPO_DT_FIM = "filter.dtFimStr"


def executar(driver, wait, relatorio_config, contexto):
    """Função principal de execução do relatório Preço Total de Vendas."""
    logger = contexto["logger"]
    normalizar_valor = contexto["normalizar_valor"]
    default_report_wait = contexto["default_report_wait"]
    marcar_inicio_download = contexto["marcar_inicio_download"]
    renomear_download = contexto["renomear_download"]

    filtros = relatorio_config.get("filtros", []) or []

    empresa = _obter_filtro_por_campo(filtros, CAMPO_EMPRESA, "cdEmpresaView")
    empreendimento = _obter_filtro_por_campo(filtros, CAMPO_EMPREENDIMENTO, "cdEmpreendView")
    dt_inicio = _obter_filtro_por_campo(filtros, CAMPO_DT_INICIO)
    dt_fim = _obter_filtro_por_campo(filtros, CAMPO_DT_FIM)

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
    empreendimentos = _extrair_valores(empreendimento)
    total = _calcular_total_iteracoes(empresas, empreendimentos)

    logger.info("Executor preco_total_vendas iniciando com %s iteracao(oes).", total)

    # Loop de iteração por empresa + empreendimento
    for index in range(total):
        if empresa:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(empresa, CAMPO_EMPRESA, "cdEmpresaView"),
                _obter_valor_iteracao(empresas, index),
                logger,
            )

        if empreendimento:
            _preencher_campo(
                driver,
                wait,
                _montar_identificadores(empreendimento, CAMPO_EMPREENDIMENTO, "cdEmpreendView"),
                _obter_valor_iteracao(empreendimentos, index),
                logger,
            )

        logger.info(
            "Executor preco_total_vendas disparando ENTER na iteracao %s/%s.",
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
        "Executor preco_total_vendas preenchendo campo %s com valor %s.",
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


def _calcular_total_iteracoes(empresas, empreendimentos):
    """Calcula total de iterações validando tamanhos iguais."""
    totais = [len(valores) for valores in (empresas, empreendimentos) if valores]
    if not totais:
        return 1

    if len(set(total for total in totais if total > 1)) > 1:
        raise ValueError(
            "Os filtros Empresa e Empreendimento do relatorio de preco total de vendas "
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


def _normalizar_texto(valor):
    return str(valor or "").strip().lower()
