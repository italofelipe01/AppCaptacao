"""Preenchimento de campos do Sienge oferecido aos executores de relatorio.

Inclui o preenchimento legado em iframe, autocomplete MUI e normalizacao de datas.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC

from app_captacao.automacao.config import BY_MAP

logger = logging.getLogger(__name__)


def preencher_campo_legado(driver, wait, filtro):
    iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
    driver.switch_to.frame(iframe)

    tipo_campo = (filtro.get("tipo_campo") or "ID").upper()
    campo_identificador = (filtro.get("campo_identificador") or "").strip()
    by = BY_MAP.get(tipo_campo, By.ID)
    valor = normalizar_valor_automacao(filtro)

    logger.info(
        "Preenchimento legado | nome=%s | tipo=%s | campo=%s | valor=%s",
        filtro.get("nome", ""),
        tipo_campo,
        campo_identificador,
        valor,
    )

    try:
        campo = driver.find_element(by, campo_identificador)
        campo.clear()
        time.sleep(1)
        campo.send_keys(valor, Keys.TAB)
        time.sleep(1)
        valor_final = (campo.get_attribute("value") or "").strip()
        logger.info(
            "Preenchimento legado concluido | campo=%s | valor_final=%s",
            campo_identificador,
            valor_final,
        )
    finally:
        driver.switch_to.default_content()


def preencher_autocomplete_com_enter(
    driver,
    wait,
    identificador,
    valor,
    by=By.ID,
    iframe_index=0,
    placeholder="",
    abrir_dropdown=False,
):
    identificador = str(identificador or "").strip()
    valor_texto = str(valor or "").strip()
    placeholder_texto = str(placeholder or "").strip()
    if (not identificador and not placeholder_texto) or not valor_texto:
        return ""

    driver.switch_to.default_content()

    if iframe_index not in (None, ""):
        _alternar_iframe(driver, wait, iframe_index)

    try:
        campo = _localizar_autocomplete(driver, wait, identificador, by, placeholder_texto)
        if abrir_dropdown:
            _clicar_dropdown_autocomplete(campo)
            _aguardar_lista_autocomplete(driver, wait)
        campo.click()
        time.sleep(0.3)
        campo.send_keys(Keys.CONTROL, "a")
        time.sleep(0.2)
        campo.send_keys(Keys.DELETE)
        time.sleep(0.2)
        campo.send_keys(valor_texto)
        _aguardar_opcao_autocomplete(driver, wait, valor_texto)

        if not _selecionar_primeira_opcao_visivel_autocomplete(driver, wait):
            if not _selecionar_opcao_autocomplete(driver, wait, valor_texto):
                campo.send_keys(Keys.ARROW_DOWN)
                time.sleep(0.3)
                campo.send_keys(Keys.ENTER)
                time.sleep(1)

        return (campo.get_attribute("value") or "").strip()
    finally:
        driver.switch_to.default_content()


def _localizar_autocomplete(driver, wait, identificador, by, placeholder_texto):
    localizadores = []
    if identificador:
        localizadores.append((by, identificador))

    if placeholder_texto:
        localizadores.append(
            (
                By.XPATH,
                f"//input[@role='combobox' and @placeholder=\"{placeholder_texto}\"]",
            )
        )

    if identificador.startswith("mui-"):
        localizadores.append(
            (
                By.XPATH,
                "//input[@role='combobox' and contains(@class,'MuiAutocomplete-input')]",
            )
        )

    ultimo_erro = None
    for localizador in localizadores:
        try:
            return wait.until(EC.element_to_be_clickable(localizador))
        except Exception as exc:
            ultimo_erro = exc

    if ultimo_erro:
        raise ultimo_erro
    raise TimeoutException("Nao foi possivel localizar o campo autocomplete.")


def _selecionar_opcao_autocomplete(driver, wait, valor_texto):
    opcoes = _montar_localizadores_opcao_autocomplete(valor_texto)

    for localizador in opcoes:
        try:
            opcao = wait.until(EC.element_to_be_clickable(localizador))
            opcao.click()
            time.sleep(1)
            return True
        except Exception:
            continue

    return False


def _selecionar_primeira_opcao_visivel_autocomplete(driver, wait):
    try:
        opcoes = wait.until(
            EC.presence_of_all_elements_located((By.XPATH, "//li[@role='option']"))
        )
    except Exception:
        return False

    for opcao in opcoes:
        try:
            if not opcao.is_displayed():
                continue
            opcao.click()
            time.sleep(1)
            return True
        except Exception:
            continue

    return False


def _aguardar_opcao_autocomplete(driver, wait, valor_texto):
    for localizador in _montar_localizadores_opcao_autocomplete(valor_texto):
        try:
            wait.until(EC.presence_of_element_located(localizador))
            time.sleep(0.5)
            return
        except Exception:
            continue


def _montar_localizadores_opcao_autocomplete(valor_texto):
    partes = [parte.strip() for parte in valor_texto.split("-") if parte.strip()]
    termo_prioritario = partes[0] if partes else valor_texto
    return [
        (
            By.XPATH,
            f"//li[@role='option' and contains(normalize-space(.), \"{valor_texto}\")]",
        ),
        (
            By.XPATH,
            f"//li[@role='option' and starts-with(normalize-space(.), \"{termo_prioritario}\")]",
        ),
        (
            By.XPATH,
            f"//li[@role='option' and contains(normalize-space(.), \"{termo_prioritario}\")]",
        ),
    ]


def _clicar_dropdown_autocomplete(campo):
    container = campo.find_element(By.XPATH, "./ancestor::div[contains(@class,'MuiAutocomplete-inputRoot')]")
    botao_abrir = container.find_element(
        By.XPATH,
        ".//button[@aria-label='Abrir' or @title='Abrir' or .//*[local-name()='svg' and @data-testid='ArrowDropDownIcon']]",
    )
    botao_abrir.click()


def _aguardar_lista_autocomplete(driver, wait):
    wait.until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//ul[@role='listbox' or contains(@class,'MuiAutocomplete-listbox')]",
            )
        )
    )
    time.sleep(0.5)


def _alternar_iframe(driver, wait, iframe_index):
    if iframe_index in (None, ""):
        return

    wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
    time.sleep(1)

    frames = driver.find_elements(By.TAG_NAME, "iframe")
    indice = int(iframe_index)
    if indice < 0 or indice >= len(frames):
        raise IndexError(f"IframeIndex {iframe_index} nao encontrado na pagina.")

    driver.switch_to.frame(frames[indice])
    time.sleep(1)


def normalizar_valor_automacao(filtro):
    valor = filtro.get("valor")
    if valor is None:
        return ""

    if (filtro.get("tipo_campo_valor") or "").strip().upper() != "DATE":
        return str(valor)

    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y")

    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")

    valor_texto = str(valor).strip()
    if not valor_texto:
        return ""

    for formato_entrada in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%d%m%Y"):
        try:
            data_convertida = datetime.strptime(valor_texto, formato_entrada)
            return data_convertida.strftime("%d/%m/%Y")
        except ValueError:
            continue

    logger.info(
        "Valor de data '%s' nao reconhecido para conversao automatica. Enviando texto original.",
        valor_texto,
    )
    return valor_texto
