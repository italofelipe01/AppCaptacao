"""
Módulo de geração do relatório "Extrato Cliente Histórico".

Este módulo automatiza a execução do relatório de extrato histórico de clientes
através de interface web utilizando Selenium. Suporta múltiplas combinações
de empresa e empreendimento, processando cada combinação em uma iteração.

Dependências:
    - selenium: Automação de navegador
    - time: Controle de temporização

Autor: Sistema de Automação de Relatórios
Data: 2026
"""
import time

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from app_captacao.automacao.navegador import fechar_janelas_extras as _fechar_janelas_extras


def executar(driver, wait, relatorio_config, contexto):
    """
    Função principal de execução do relatório Extrato Cliente Histórico.
    
    Esta função coordena todo o processo de geração do relatório, desde a
    leitura dos filtros até o download dos arquivos gerados. Utiliza o padrão
    de configuração legado (versão antiga) para preenchimento dos campos.
    
    Args:
        driver: Instância do WebDriver do Selenium para controle do navegador.
        wait: Instância de WebDriverWait para espera explícita de elementos.
        relatorio_config: Dicionário contendo configuração do relatório e filtros.
        contexto: Dicionário com utilitários compartilhados (logger, normalizadores, etc).
    
    O contexto deve conter:
        - logger: Instância de logger para registro de mensagens
        - normalizar_valor: Função para normalizar valores de data
        - default_report_wait: Tempo padrão de espera entre operações
        - marcar_inicio_download: Função para marcar timestamp de início de download
        - renomear_download: Função para renomear arquivo baixado
    """
    logger = contexto["logger"]
    normalizar_valor = contexto["normalizar_valor"]
    default_report_wait = contexto["default_report_wait"]
    marcar_inicio_download = contexto["marcar_inicio_download"]
    renomear_download = contexto["renomear_download"]

    filtros = relatorio_config.get("filtros", []) or []

    # Extração dos filtros de data e entidades
    # Estes filtros são definidos na configuração do relatório e mapeados
    # para os campos correspondentes na interface web
    dt_inicio = _obter_filtro_por_campo(filtros, "filter.dtVenctoInicio")
    dt_fim = _obter_filtro_por_campo(filtros, "filter.dtVenctoFim")
    dt_correcao = _obter_filtro_por_campo(filtros, "filter.dtCorrecao")
    empresa = _obter_filtro_por_campo(filtros, "filter.empresa.cdEmpresaView")
    empreendimento = _obter_filtro_por_campo(filtros, "filter.empreend.cdEmpreendView")

    # Preenchimento dos campos de data de vencimento
    # O campo de data de correção utiliza estratégia diferente (By.NAME)
    if dt_inicio:
        _preencher_campo_legado(driver, wait, "filter.dtVenctoInicio", normalizar_valor(dt_inicio), By.ID, logger)

    if dt_fim:
        _preencher_campo_legado(driver, wait, "filter.dtVenctoFim", normalizar_valor(dt_fim), By.ID, logger)

    if dt_correcao:
        _preencher_campo_legado(
            driver,
            wait,
            "filter.dtCorrecao",
            normalizar_valor(dt_correcao),
            By.NAME,  # Diferente dos outros campos, usa name ao invés de ID
            logger,
        )

    # Extração dos valores de empresa e empreendimento para iteração
    # O relatório suporta múltiplas empresas e empreendimentos, processados em
    # pares (mesmo índice). Um valor único vale para todas as iterações; listas
    # de tamanhos diferentes são erro de cadastro, não motivo para descartar valores.
    empresas = _extrair_valores(empresa)
    empreendimentos = _extrair_valores(empreendimento)
    total = _calcular_pares_empresa_empreendimento(empresas, empreendimentos)
    if len(empresas) == 1:
        empresas = empresas * total
    if len(empreendimentos) == 1:
        empreendimentos = empreendimentos * total

    logger.info(
        "Executor extrato_cliente_historico em modo versaoantiga com %s iteracao(oes).",
        total,
    )

    index = 0
    while index < total:
        # Preenchimento de cada par empresa/empreendimento
        # O campo de empresa usa o identificador completo com prefixo 'filter.empresa'
        # enquanto o empreendimento usa 'filter.empreend'
        _preencher_campo_legado(
            driver,
            wait,
            "filter.empresa.cdEmpresaView",
            str(empresas[index]),
            By.ID,
            logger,
        )

        _preencher_campo_legado(
            driver,
            wait,
            "filter.empreend.cdEmpreendView",
            str(empreendimentos[index]),
            By.ID,
            logger,
        )

        # Dispara a geração do relatório pressionando ENTER
        # Após o ENTER, o sistema processa e inicia o download
        logger.info(
            "Executor extrato_cliente_historico disparando ENTER do loop %s/%s.",
            index + 1,
            total,
        )
        inicio_download = marcar_inicio_download()
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(default_report_wait)
        _fechar_janelas_extras(driver)  # Fecha popup/janela extra aberta pelo relatório
        renomear_download(relatorio_config, str(empresas[index]), inicio_download)

        index += 1


def _calcular_pares_empresa_empreendimento(empresas, empreendimentos):
    """Quantidade de pares empresa/empreendimento a executar."""
    if not empresas or not empreendimentos:
        raise ValueError(
            "O extrato de cliente historico precisa de empresa e empreendimento preenchidos."
        )
    if len(empresas) > 1 and len(empreendimentos) > 1 and len(empresas) != len(empreendimentos):
        raise ValueError(
            "Os filtros Empresa e Empreendimento do extrato de cliente historico possuem "
            f"quantidades de valores diferentes ({len(empresas)} e {len(empreendimentos)})."
        )
    return max(len(empresas), len(empreendimentos))


def _obter_filtro_por_campo(filtros, campo_identificador):
    """
    Busca um filtro específico na lista de filtros pela identificação do campo.
    
    A comparação é feita de forma normalizada (case-insensitive) para evitar
    problemas com variações de capitalização nos identificadores.
    
    Args:
        filtros: Lista de dicionários contendo os filtros configurados.
        campo_identificador: String com o identificador do campo a buscar.
    
    Returns:
        Dicionário do filtro encontrado ou None se não existir.
    """
    campo_normalizado = str(campo_identificador or "").strip().lower()
    for filtro in filtros:
        if str(filtro.get("campo_identificador") or "").strip().lower() == campo_normalizado:
            return filtro
    return None


def _extrair_valores(filtro):
    """
    Extrai os valores de um filtro, convertendo para lista de strings.
    
    O filtro pode conter valores em formato de lista ou string separada por vírgulas.
    Esta função normaliza ambos os formatos para uma lista consistente de strings.
    
    Args:
        filtro: Dicionário do filtro contendo chave 'valor' com os dados.
    
    Returns:
        Lista de strings com os valores extraídos e limpos (sem espaços extras).
    """
    if not filtro:
        return []

    valor = filtro.get("valor")
    if isinstance(valor, list):
        # Formato lista: processa cada item individualmente
        return [str(item).strip() for item in valor if str(item).strip()]

    # Formato string separada por vírgulas: divide e processa
    return [parte.strip() for parte in str(valor or "").split(",") if parte.strip()]


def _preencher_campo_legado(driver, wait, identificador, valor, by, logger):
    """
    Preenche um campo utilizando a estratégia legada (versão antiga do sistema).
    
    Esta abordagem utiliza iframes para localizar os elementos, que é necessária
    para sistemas mais antigos que renderizam seus formulários dentro de iframes.
    
    Args:
        driver: Instância do WebDriver do Selenium.
        wait: Instância de WebDriverWait para esperas explícitas.
        identificador: ID ou nome do campo a preencher.
        valor: Valor a ser inserido no campo.
        by: Tipo de localizador (By.ID, By.NAME, etc).
        logger: Instância de logger para mensagens.
    """
    # Localiza o primeiro iframe da página e entra nele:
    # muitos sistemas legados renderizam formulários dentro de iframes
    iframe = wait.until(lambda current_driver: current_driver.find_element(By.TAG_NAME, "iframe"))
    driver.switch_to.frame(iframe)

    logger.info(
        "Modulo extrato_cliente_historico preenchendo no estilo antigo | by=%s | campo=%s | valor=%s",
        by,
        identificador,
        valor,
    )

    try:
        campo = driver.find_element(by, identificador)
        campo.clear()
        time.sleep(1)
        # Envia o valor seguido de TAB para confirmar e mover para próximo campo
        campo.send_keys(str(valor or ""), Keys.TAB)
        time.sleep(1)
    finally:
        driver.switch_to.default_content()  # Retorna ao contexto principal
        time.sleep(1)
