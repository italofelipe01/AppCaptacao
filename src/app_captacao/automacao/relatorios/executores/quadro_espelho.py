import math
import time
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app_captacao.automacao.relatorios.executores.extrato_saldo_devedor_presente import (
    PAUSA_INICIO_DOWNLOAD,
    TAMANHO_PAGINA,
    TIMEOUT_LOCALIZACAO_CAMPO,
    _aguardar_grade_pronta,
    _clicar_botao_gerar_relatorio,
    _extrair_valores,
    _fechar_janelas_extras,
    _ir_para_proxima_pagina,
    _log_etapa,
    _log_filtros_recebidos,
    _montar_sufixo_exportacao,
    _normalizar_texto,
    _obter_filtro_por_campo,
    _obter_filtro_por_nome,
    _obter_identificador_principal,
    _obter_total_registros,
    _obter_valor_iteracao,
    _registrar_arquivo_final,
    _selecionar_formato_excel_na_modal,
    _selecionar_tamanho_pagina,
)


CAMPO_GRUPO_EMPRESA = "filter.grupoEmpresa.grupoEmpresaPK.cdGrupoEmpresa"
IDENTIFICADORES_GRUPO_EMPRESA = (
    "filter.grupoEmpresa.grupoEmpresaPK.cdGrupoEmpresa",
    "cdGrupoEmpresa",
    "grupoEmpresaPK.cdGrupoEmpresa",
)
CAMPO_EMPRESA = "filter.empresa.cdEmpresaView"
IDENTIFICADORES_EMPRESA = ("filter.empresa.cdEmpresaView", "cdEmpresaView")
CAMPO_EMPREENDIMENTO = "filter.empreend.cdEmpreendView"
IDENTIFICADORES_EMPREENDIMENTO = ("filter.empreend.cdEmpreendView", "cdEmpreendView")
# A tela do Quadro espelho (inclusive a aba Lista) nao tem campo de data: conferido em 2026-10-20.


def executar(driver, wait, relatorio_config, contexto):
    logger = contexto["logger"]
    normalizar_valor = contexto["normalizar_valor"]
    preencher_autocomplete_enter = contexto["preencher_autocomplete_enter"]
    marcar_inicio_download = contexto["marcar_inicio_download"]
    renomear_download = contexto["renomear_download"]
    sanitizar_nome_arquivo = contexto["sanitizar_nome_arquivo"]
    copiar_download_para_sharepoint = contexto["copiar_download_para_sharepoint"]
    montar_caminho_download_unico = contexto["montar_caminho_download_unico"]
    capture_debug_snapshot = contexto["capture_debug_snapshot"]
    download_dir = Path(contexto["download_dir"])

    filtros = relatorio_config.get("filtros", []) or []
    _log_filtros_recebidos(logger, filtros)

    grupo_empresa = _obter_filtro_por_campo(filtros, CAMPO_GRUPO_EMPRESA, *IDENTIFICADORES_GRUPO_EMPRESA)
    empresa = _obter_filtro_por_campo(filtros, CAMPO_EMPRESA, *IDENTIFICADORES_EMPRESA)
    empreendimento = _obter_filtro_por_campo(filtros, CAMPO_EMPREENDIMENTO, *IDENTIFICADORES_EMPREENDIMENTO)

    if not grupo_empresa:
        grupo_empresa = _obter_filtro_por_nome(filtros, "grupo")
    if not empresa:
        empresa = _obter_filtro_por_nome(filtros, "empresa")
    if not empreendimento:
        empreendimento = _obter_filtro_por_nome(filtros, "empreendimento")

    grupos_empresa = _extrair_valores(grupo_empresa)
    empresas = _extrair_valores(empresa)
    empreendimentos = _extrair_valores(empreendimento)

    total = _calcular_total_iteracoes(grupos_empresa, empresas, empreendimentos)

    logger.info(
        "Executor quadro_espelho iniciando | grupos=%s | empresas=%s | empreendimento=%s | iteracoes=%s",
        grupos_empresa or [""],
        empresas or [""],
        empreendimentos or [""],
        total,
    )

    for index in range(total):
        iteracao = index + 1
        valor_grupo_empresa = _obter_valor_iteracao(grupos_empresa, index)
        valor_empresa = _obter_valor_iteracao(empresas, index)
        valor_empreendimento = _obter_valor_iteracao(empreendimentos, index)

        _log_etapa(logger, iteracao, "inicio", "iniciando fluxo do relatorio quadro espelho")
        _abrir_aba_lista(driver, logger)
        capture_debug_snapshot(f"quadro_espelho_inicio_iteracao_{iteracao}")

        _preparar_filtros_relatorio(
            driver,
            wait,
            normalizar_valor,
            preencher_autocomplete_enter,
            grupo_empresa,
            valor_grupo_empresa,
            empresa,
            valor_empresa,
            empreendimento,
            valor_empreendimento,
            logger,
            iteracao,
            capture_debug_snapshot,
        )

        _log_etapa(logger, iteracao, "paginacao", f"ajustando paginacao para {TAMANHO_PAGINA}")
        _selecionar_tamanho_pagina(driver, wait, logger, TAMANHO_PAGINA)
        capture_debug_snapshot(f"quadro_espelho_paginacao_5000_iteracao_{iteracao}")
        total_registros = _obter_total_registros(driver, wait, logger)
        total_paginas = max(1, math.ceil(total_registros / int(TAMANHO_PAGINA)))
        _log_etapa(
            logger,
            iteracao,
            "paginacao",
            f"total de registros={total_registros}; total de paginas para exportacao={total_paginas}",
        )

        arquivos_baixados = []
        for pagina in range(total_paginas):
            numero_pagina = pagina + 1
            _log_etapa(
                logger,
                iteracao,
                "exportacao",
                f"iniciando exportacao da pagina {numero_pagina}/{total_paginas}",
            )
            inicio_download = marcar_inicio_download()
            _clicar_botao_gerar_relatorio(driver, wait, logger)
            capture_debug_snapshot(f"quadro_espelho_modal_exportacao_iteracao_{iteracao}_pagina_{numero_pagina}")
            _selecionar_formato_excel_na_modal(driver, logger)
            time.sleep(PAUSA_INICIO_DOWNLOAD)

            arquivo_baixado = renomear_download(
                relatorio_config,
                _montar_sufixo_exportacao(valor_empresa or valor_grupo_empresa, numero_pagina),
                inicio_download,
                registrar_resultado=False,
            )
            _fechar_janelas_extras(driver)
            if arquivo_baixado:
                arquivos_baixados.append(Path(arquivo_baixado))

            if pagina < total_paginas - 1:
                _log_etapa(logger, iteracao, "paginacao", f"avancando para a proxima pagina apos exportar a pagina {numero_pagina}")
                _ir_para_proxima_pagina(driver, logger)

        _registrar_arquivo_final(
            arquivos_baixados,
            relatorio_config,
            valor_empresa or valor_grupo_empresa,
            download_dir,
            sanitizar_nome_arquivo,
            montar_caminho_download_unico,
            copiar_download_para_sharepoint,
            logger,
        )


def _abrir_aba_lista(driver, logger):
    driver.switch_to.default_content()
    localizadores = [
        (By.XPATH, "//button[@role='tab' and normalize-space(.)='Lista']"),
        (By.XPATH, "//button[contains(@class,'MuiTab-root') and normalize-space(.)='Lista']"),
    ]

    for localizador in localizadores:
        try:
            botao = WebDriverWait(driver, TIMEOUT_LOCALIZACAO_CAMPO).until(EC.element_to_be_clickable(localizador))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao)
            try:
                botao.click()
            except Exception:
                driver.execute_script("arguments[0].click();", botao)
            time.sleep(1)
            logger.info("Aba 'Lista' acionada com sucesso.")
            return
        except Exception:
            continue

    logger.info("Aba 'Lista' nao encontrada; seguindo fluxo.")


def _preparar_filtros_relatorio(
    driver,
    wait,
    normalizar_valor,
    preencher_autocomplete_enter,
    filtro_grupo_empresa,
    valor_grupo_empresa,
    filtro_empresa,
    valor_empresa,
    filtro_empreendimento,
    valor_empreendimento,
    logger,
    iteracao,
    capture_debug_snapshot,
):
    if filtro_grupo_empresa and valor_grupo_empresa:
        _log_etapa(logger, iteracao, "grupo_empresa", f"preenchendo grupo de empresa com {valor_grupo_empresa}")
        _preencher_autocomplete_por_placeholder(
            driver,
            wait,
            preencher_autocomplete_enter,
            filtro_grupo_empresa,
            valor_grupo_empresa,
            "Pesquisar grupo empresa",
            logger,
        )
        capture_debug_snapshot(f"quadro_espelho_grupo_empresa_iteracao_{iteracao}")

    if filtro_empresa and valor_empresa:
        _log_etapa(logger, iteracao, "empresa", f"preenchendo empresa com {valor_empresa}")
        _preencher_autocomplete_por_placeholder(
            driver,
            wait,
            preencher_autocomplete_enter,
            filtro_empresa,
            valor_empresa,
            "Pesquisar empresa",
            logger,
        )
        capture_debug_snapshot(f"quadro_espelho_empresa_iteracao_{iteracao}")

    if filtro_empreendimento and valor_empreendimento:
        _log_etapa(logger, iteracao, "empreendimento", f"preenchendo empreendimento com {valor_empreendimento}")
        _preencher_autocomplete_por_placeholder(
            driver,
            wait,
            preencher_autocomplete_enter,
            filtro_empreendimento,
            valor_empreendimento,
            "Pesquisar empreendimento",
            logger,
        )
        capture_debug_snapshot(f"quadro_espelho_empreendimento_iteracao_{iteracao}")

    _clicar_botao_consultar_generico(driver, logger)
    _aguardar_grade_pronta(driver, logger)


def _preencher_autocomplete_por_placeholder(
    driver,
    wait,
    preencher_autocomplete_enter,
    filtro,
    valor,
    placeholder,
    logger,
):
    try:
        preencher_autocomplete_enter(
            driver,
            wait,
            _obter_identificador_principal(filtro),
            valor,
            placeholder=placeholder,
            abrir_dropdown=True,
        )
    except Exception as exc:
        logger.info(
            "Falha ao preencher autocomplete %s com placeholder %s: %s",
            valor,
            placeholder,
            type(exc).__name__,
        )
        raise


def _clicar_botao_consultar_generico(driver, logger):
    driver.switch_to.default_content()
    localizadores = [
        (By.XPATH, "//button[normalize-space(.)='Consultar']"),
        (By.XPATH, "//button[@type='submit' and normalize-space(.)='Consultar']"),
    ]

    for localizador in localizadores:
        try:
            botao = WebDriverWait(driver, TIMEOUT_LOCALIZACAO_CAMPO).until(EC.element_to_be_clickable(localizador))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao)
            try:
                botao.click()
            except Exception:
                driver.execute_script("arguments[0].click();", botao)
            time.sleep(1)
            logger.info("Botao 'Consultar' clicado com sucesso.")
            return
        except Exception:
            continue

    raise TimeoutError("Nao foi possivel localizar o botao Consultar do quadro espelho.")


def _calcular_total_iteracoes(*listas_valores):
    totais = [len(valores) for valores in listas_valores if valores]
    if not totais:
        return 1

    if len(set(total for total in totais if total > 1)) > 1:
        raise ValueError(
            "Os filtros Grupo de empresa, Empresa e Empreendimento do relatorio de quadro espelho "
            "possuem quantidades de valores diferentes."
        )

    return max(totais)
