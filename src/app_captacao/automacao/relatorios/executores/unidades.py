import time
import unicodedata

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from app_captacao.automacao.navegador import fechar_janelas_extras as _fechar_janelas_extras


SELECAO_CAMPO = "filter.selecao"
SELECAO_VALOR = "por Empreendimento"
GRUPO_EMPRESA_CAMPO = "filter.grupoEmpresa.grupoEmpresaPK.cdGrupoEmpresa"
# "Posição em*" da tela (page/811). Vazio, o Sienge usa a data do dia.
POSICAO_EM_CAMPO = "filter.dtHistorica"
POSICAO_EM_NOME = "posicao em"


def executar(driver, wait, relatorio_config, contexto):
    logger = contexto["logger"]
    normalizar_valor = contexto["normalizar_valor"]
    default_report_wait = contexto["default_report_wait"]
    marcar_inicio_download = contexto["marcar_inicio_download"]
    renomear_download = contexto["renomear_download"]

    filtros = relatorio_config.get("filtros", []) or []

    # A tela (page/811) nao tem periodo nem "Tipo de relatorio": so os campos abaixo existem.
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
    # O catalogo pode identificar o filtro pelo campo ou so pelo nome "Posição em".
    posicao_em = _obter_filtro_por_campo(filtros, POSICAO_EM_CAMPO, "dtHistorica") or _obter_filtro_por_nome(
        filtros, POSICAO_EM_NOME
    )
    # O campo da tela e sempre data: valor ISO da tela do app vira dd/mm/aaaa mesmo sem TipoCampoValor DATE.
    valor_posicao_em = normalizar_valor({**posicao_em, "tipo_campo_valor": "DATE"}).strip() if posicao_em else ""
    if not valor_posicao_em:
        logger.info("Executor unidades sem valor para Posicao em; o Sienge usa a data padrao da tela.")

    logger.info("Executor unidades aplicando selects padrao do backend.")
    _selecionar_select(driver, wait, SELECAO_CAMPO, SELECAO_VALOR, logger)
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

    grupos_empresa = _extrair_valores(grupo_empresa)
    empresas = _extrair_valores(empresa)
    empreendimentos = _extrair_valores(empreendimento)
    total = _calcular_total_iteracoes(grupos_empresa, empresas, empreendimentos)

    logger.info("Executor unidades iniciando com %s iteracao(oes).", total)

    for index in range(total):
        # Antes dos lookups: o ENTER continua saindo do campo de empreendimento.
        if valor_posicao_em:
            _preencher_campo(driver, wait, [POSICAO_EM_CAMPO], valor_posicao_em, logger)

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

        if valor_posicao_em:
            _confirmar_valor_na_tela(driver, wait, POSICAO_EM_CAMPO, valor_posicao_em, "Posicao em")

        logger.info("Executor unidades disparando ENTER na iteracao %s/%s.", index + 1, total)
        inicio_download = marcar_inicio_download()
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(default_report_wait)
        renomear_download(relatorio_config, _obter_valor_iteracao(empresas, index), inicio_download)
        _fechar_janelas_extras(driver)


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


def _obter_filtro_por_nome(filtros, trecho_nome):
    trecho = _sem_acento(trecho_nome)
    for filtro in filtros:
        if trecho and trecho in _sem_acento(filtro.get("nome") or filtro.get("nome_filtro")):
            return filtro
    return None


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


def _selecionar_select(driver, wait, identificador, valor, logger):
    elemento = _localizar_no_primeiro_iframe(driver, wait, identificador)
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


def _confirmar_valor_na_tela(driver, wait, identificador, valor_esperado, rotulo):
    """Sem o valor na tela o Sienge gera o relatorio com o padrao dele: melhor falhar do que baixar errado."""
    try:
        valor_na_tela = str(_localizar_no_primeiro_iframe(driver, wait, identificador).get_attribute("value") or "")
    finally:
        driver.switch_to.default_content()

    if valor_na_tela.strip() != valor_esperado:
        raise ValueError(
            f"O campo {rotulo} do relatorio de unidades ficou com '{valor_na_tela.strip()}' "
            f"na tela do Sienge, e nao com '{valor_esperado}'."
        )


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


def _normalizar_texto(valor):
    return str(valor or "").strip().lower()


def _sem_acento(valor):
    texto = unicodedata.normalize("NFKD", _normalizar_texto(valor))
    return " ".join("".join(caractere for caractere in texto if not unicodedata.combining(caractere)).split())
