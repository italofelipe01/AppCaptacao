"""Criacao do WebDriver (Edge padrao, Chrome opcional) e utilitarios de janela.

Edge nao cai para Chrome em caso de falha: o navegador e escolhido so por
SELENIUM_BROWSER.
"""

from __future__ import annotations

import logging
import shutil
import socket
import subprocess
import time
import os
import weakref
from pathlib import Path
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from app_captacao.automacao.config import (
    ATTACH_NORMAL_CHROME,
    ATTACH_NORMAL_EDGE,
    CHROME_DEBUG_HOST,
    CHROME_DEBUG_PORT,
    CHROME_PROFILE_DIRECTORY,
    CHROME_USER_DATA_DIR,
    DEFAULT_TIMEOUT,
    DOWNLOAD_DIR,
    EDGE_DEBUG_HOST,
    EDGE_DEBUG_PORT,
    EDGE_PROFILE_DIRECTORY,
    EDGE_USE_PROFILE,
    EDGE_USER_DATA_DIR,
    KEEP_BROWSER_OPEN,
    LOGIN_URL,
    REPORT_READY_TIMEOUT,
    SELENIUM_BROWSER,
)

logger = logging.getLogger(__name__)

_PREFIXOS_PAGINA_INTERNA = ("edge://", "chrome://", "devtools://", "chrome-extension://", "extension://")


def _configurar_browser_options(options):
    options.add_argument("--start-maximized")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(Path(DOWNLOAD_DIR).resolve()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )
    options.add_experimental_option("detach", KEEP_BROWSER_OPEN)
    return options


def _aguardar_porta_debug(host, port, timeout_seconds=15):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.4)
    return False


def _get_chrome_path():
    chrome_candidates = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        shutil.which("google-chrome"),
        os.path.join(os.getenv("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.getenv("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]

    for candidate in chrome_candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


def _get_edge_path():
    edge_candidates = [
        shutil.which("msedge"),
        shutil.which("msedge.exe"),
        os.path.join(os.getenv("PROGRAMFILES(X86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.getenv("PROGRAMFILES", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    for candidate in edge_candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


def _anexar_ao_chrome_normal():
    chrome_path = _get_chrome_path()
    if not chrome_path:
        raise FileNotFoundError("Chrome nao encontrado para anexar via depuracao remota.")

    if not _aguardar_porta_debug(CHROME_DEBUG_HOST, CHROME_DEBUG_PORT, timeout_seconds=1):
        comando = [
            chrome_path,
            f"--remote-debugging-port={CHROME_DEBUG_PORT}",
            f"--remote-debugging-address={CHROME_DEBUG_HOST}",
        ]
        if CHROME_USER_DATA_DIR:
            comando.append(f"--user-data-dir={CHROME_USER_DATA_DIR}")
        if CHROME_PROFILE_DIRECTORY:
            comando.append(f"--profile-directory={CHROME_PROFILE_DIRECTORY}")
        comando.append(LOGIN_URL)

        logger.info(
            "Abrindo Chrome normal para depuracao remota | host=%s | port=%s",
            CHROME_DEBUG_HOST,
            CHROME_DEBUG_PORT,
        )
        subprocess.Popen(comando)

    if not _aguardar_porta_debug(CHROME_DEBUG_HOST, CHROME_DEBUG_PORT, timeout_seconds=15):
        raise RuntimeError("Chrome nao abriu a porta de depuracao remota no tempo esperado.")

    options = _configurar_browser_options(webdriver.ChromeOptions())
    options.add_experimental_option(
        "debuggerAddress",
        f"{CHROME_DEBUG_HOST}:{CHROME_DEBUG_PORT}",
    )
    logger.info(
        "Anexando Selenium a instancia existente do Chrome | debuggerAddress=%s:%s",
        CHROME_DEBUG_HOST,
        CHROME_DEBUG_PORT,
    )
    driver = webdriver.Chrome(options=options)

    try:
        _posicionar_na_aba_web(driver)
        driver.get(LOGIN_URL)
        logger.info(
            "Driver anexado ao Chrome e posicionado na aba web com a URL de login do Sienge."
        )
    except Exception:
        logger.exception("Falha ao posicionar o driver anexado na aba correta do Chrome.")

    return driver


def _configurar_edge_profile(options):
    if not EDGE_USE_PROFILE:
        logger.info("Edge configurado para iniciar sem perfil local do usuario.")
        return options

    user_data_dir = str(EDGE_USER_DATA_DIR or "").strip()
    profile_directory = str(EDGE_PROFILE_DIRECTORY or "").strip()

    if not user_data_dir:
        logger.warning("EDGE_USER_DATA_DIR nao definido. Edge iniciara sem perfil local.")
        return options

    caminho_perfil = Path(user_data_dir).expanduser().resolve()
    caminho_perfil.mkdir(parents=True, exist_ok=True)

    options.add_argument(f"--user-data-dir={caminho_perfil}")
    if profile_directory:
        options.add_argument(f"--profile-directory={profile_directory}")

    logger.info(
        "Edge iniciara com perfil local | user_data_dir=%s | profile=%s",
        caminho_perfil,
        profile_directory or "Default",
    )
    return options


# Drivers ligados ao Edge da automacao pela porta de depuracao: neles quit() so desconecta.
_drivers_edge_anexado: "weakref.WeakSet[object]" = weakref.WeakSet()


def _anexar_ao_edge_normal():
    edge_path = _get_edge_path()
    if not edge_path:
        raise FileNotFoundError("Microsoft Edge nao encontrado para anexar via depuracao remota.")

    caminho_perfil = Path(EDGE_USER_DATA_DIR).expanduser().resolve()
    caminho_perfil.mkdir(parents=True, exist_ok=True)

    if not _aguardar_porta_debug(EDGE_DEBUG_HOST, EDGE_DEBUG_PORT, timeout_seconds=1):
        comando = [
            edge_path,
            f"--remote-debugging-port={EDGE_DEBUG_PORT}",
            f"--remote-debugging-address={EDGE_DEBUG_HOST}",
            f"--user-data-dir={caminho_perfil}",
            f"--profile-directory={EDGE_PROFILE_DIRECTORY}",
            "--no-first-run",
            "--no-default-browser-check",
            LOGIN_URL,
        ]
        logger.info(
            "Abrindo Edge normal para depuracao remota | host=%s | port=%s | profile=%s",
            EDGE_DEBUG_HOST,
            EDGE_DEBUG_PORT,
            caminho_perfil,
        )
        subprocess.Popen(comando)

    if not _aguardar_porta_debug(EDGE_DEBUG_HOST, EDGE_DEBUG_PORT, timeout_seconds=20):
        raise RuntimeError("Edge nao abriu a porta de depuracao remota no tempo esperado.")

    options = webdriver.EdgeOptions()
    options.add_experimental_option(
        "debuggerAddress",
        f"{EDGE_DEBUG_HOST}:{EDGE_DEBUG_PORT}",
    )
    driver = webdriver.Edge(options=options)
    _drivers_edge_anexado.add(driver)

    pasta_downloads = str(Path(DOWNLOAD_DIR).resolve())
    try:
        driver.execute_cdp_cmd(
            "Browser.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": pasta_downloads, "eventsEnabled": True},
        )
    except Exception as exc:
        # Sem isto o Edge baixa na pasta padrao dele e nenhum relatorio e encontrado depois.
        raise RuntimeError(
            f"Nao foi possivel apontar os downloads do Edge para {pasta_downloads}."
        ) from exc
    logger.info("Downloads do Edge apontados para %s.", pasta_downloads)

    _posicionar_na_aba_web(driver)
    logger.info("Selenium anexado ao Edge normal existente na porta %s.", EDGE_DEBUG_PORT)
    return driver


# Aba do Sienge escolhida para cada driver. Guardada fora do driver porque a janela
# "atual" do Selenium pode ficar num dialogo interno do Edge depois de uma falha.
_janela_principal: "weakref.WeakKeyDictionary[object, str]" = weakref.WeakKeyDictionary()


def _url_eh_interna(url) -> bool:
    return str(url or "").strip().lower().startswith(_PREFIXOS_PAGINA_INTERNA)


def _urls_das_janelas(driver) -> dict[str, str]:
    """URL de cada janela, lida pelo DevTools sem trocar de janela.

    No Chromium o handle da janela e o targetId do DevTools. Trocar para um dialogo
    interno do Edge (edge://sync-confirmation-dialog/) e tentar fechar trava 20 s e
    pode derrubar a sessao do Selenium.
    """
    try:
        resposta = driver.execute_cdp_cmd("Target.getTargets", {})
    except Exception:
        return {}
    if not isinstance(resposta, dict):
        return {}
    urls = {}
    for alvo in resposta.get("targetInfos") or []:
        if isinstance(alvo, dict) and alvo.get("targetId"):
            urls[str(alvo["targetId"]).upper()] = str(alvo.get("url") or "")
    return urls


def _url_da_janela(driver, handle, urls) -> str | None:
    """URL da janela; None se nao der para saber sem risco."""
    url = urls.get(str(handle).upper())
    if url is not None:
        return url
    try:
        driver.switch_to.window(handle)
        return str(driver.current_url or "")
    except WebDriverException:
        return None


def _escolher_aba_web(driver) -> str | None:
    host_sienge = (urlsplit(LOGIN_URL).hostname or "").lower()
    urls = _urls_das_janelas(driver)
    aba_web = None
    for handle in list(driver.window_handles):
        url = _url_da_janela(driver, handle, urls)
        if url is None or _url_eh_interna(url):
            continue
        aba_web = aba_web or handle
        if host_sienge and (urlsplit(url.lower()).hostname or "") == host_sienge:
            return handle
    return aba_web


def _posicionar_na_aba_web(driver):
    """Coloca o driver numa aba de pagina web, de preferencia a do Sienge, e maximiza.

    O navegador anexado tambem expoe dialogos internos como janelas: num Windows
    ligado ao Entra ID, o perfil novo do Edge entra sozinho na conta e abre
    edge://sync-confirmation-dialog/. Maximizar esse dialogo falha com
    "Browser window not found".
    """
    aba = _escolher_aba_web(driver)
    if aba:
        driver.switch_to.window(aba)
    else:
        driver.switch_to.new_window("tab")
    _janela_principal[driver] = driver.current_window_handle

    try:
        driver.maximize_window()
    except WebDriverException:
        logger.warning("Nao foi possivel maximizar a janela do navegador anexado; seguindo assim mesmo.")


def definir_janela_principal(driver) -> None:
    """Guarda a aba atual (a do Sienge, depois do login) como a janela de trabalho."""
    try:
        handle = driver.current_window_handle
    except WebDriverException:
        return
    if not _url_eh_interna(_urls_das_janelas(driver).get(str(handle).upper(), "")):
        _janela_principal[driver] = handle


def janela_principal(driver) -> str:
    """Aba de trabalho do Sienge; se ela sumiu, escolhe outra aba web (ou abre uma)."""
    handles = list(driver.window_handles)
    guardada = _janela_principal.get(driver)
    if guardada and guardada in handles:
        return guardada
    _posicionar_na_aba_web(driver)
    return _janela_principal[driver]


def voltar_para_janela_principal(driver) -> None:
    driver.switch_to.window(janela_principal(driver))
    driver.switch_to.default_content()


def sessao_do_driver_ativa(driver) -> bool:
    """False quando a sessao do Selenium caiu (invalid session id, navegador fechado)."""
    try:
        return bool(driver.window_handles)
    except WebDriverException:
        return False


def encerrar_driver(driver, fechar_edge_anexado: bool = True) -> None:
    """Encerra a sessao do Selenium; no Edge anexado tambem fecha o Edge da automacao.

    Anexado pela porta de depuracao, quit() so desconecta o msedgedriver e o Edge fica
    aberto na pagina do Sienge. Browser.close fecha essa instancia, que usa o perfil
    exclusivo da automacao, nunca o Edge pessoal. Chrome anexado pode estar no perfil
    pessoal e so e desconectado.
    """
    if fechar_edge_anexado and driver in _drivers_edge_anexado:
        try:
            driver.execute_cdp_cmd("Browser.close", {})
            logger.info("Edge da automacao fechado.")
        except Exception:
            logger.warning("Nao foi possivel fechar o Edge da automacao pelo DevTools.", exc_info=True)
    driver.quit()


def _criar_driver_edge():
    if ATTACH_NORMAL_EDGE:
        return _anexar_ao_edge_normal()

    options = _configurar_browser_options(webdriver.EdgeOptions())
    options = _configurar_edge_profile(options)
    return webdriver.Edge(options=options)


def _criar_driver_chrome():
    if ATTACH_NORMAL_CHROME:
        return _anexar_ao_chrome_normal()

    options = _configurar_browser_options(webdriver.ChromeOptions())
    return webdriver.Chrome(options=options)


def criar_driver():
    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

    browser = SELENIUM_BROWSER or "edge"
    if browser == "chrome":
        logger.info("Inicializando Selenium com Chrome.")
        return _criar_driver_chrome()

    if browser == "edge":
        logger.info("Inicializando Selenium exclusivamente com Edge.")
        return _criar_driver_edge()

    raise ValueError(
        "Navegador Selenium nao suportado. Configure SELENIUM_BROWSER como "
        f"'edge' ou 'chrome'; valor recebido: {browser!r}."
    )


# Iframe do formulario nas telas antigas do Sienge. A pagina tambem tem iframes de widgets
# (novidades, chat): numa maquina lenta eles aparecem antes, e entrar neles fazia cada campo
# esperar o timeout inteiro antes de tentar de novo.
IFRAME_DO_RELATORIO = "iFramePage"
_MARCA_IFRAME_ANTERIOR = "data-appcaptacao-tela-anterior"
# Folga para os scripts de carga da tela antiga, que seguem rodando depois de o documento
# completar (selects dependentes, listas carregadas por AJAX). Com 1 s, o Analitico de
# apropriacoes nao gerou o arquivo em duas execucoes de 2026-10-20; com os 6 s de antes, gerou.
PAUSA_APOS_TELA_PRONTA = 6.0
# Sem iFramePage depois disto (tela fora do padrao), vale o primeiro iframe, como antes.
_TOLERANCIA_SEM_IFRAME_DO_RELATORIO = 3.0

_FORMULARIO_PRONTO_JS = r"""
const quadro = document.getElementById(arguments[0]);
if (!quadro || quadro.hasAttribute(arguments[1])) return false;
let doc = null;
try { doc = quadro.contentDocument; } catch (e) { return false; }
return !!doc && doc.readyState === 'complete'
  && doc.querySelectorAll('input:not([type=hidden]), select, textarea').length > 0;
"""


def iframe_do_relatorio(driver, wait):
    """O iframe do formulario do relatorio (iFramePage), nunca o de um widget da pagina."""
    inicio = time.monotonic()

    def localizar(current_driver):
        quadros = current_driver.find_elements(By.ID, IFRAME_DO_RELATORIO)
        if quadros:
            return quadros[0]
        if time.monotonic() - inicio >= _TOLERANCIA_SEM_IFRAME_DO_RELATORIO:
            todos = current_driver.find_elements(By.TAG_NAME, "iframe")
            if todos:
                return todos[0]
        return False

    return wait.until(localizar)


def abrir_relatorio(driver, url, timeout: float = REPORT_READY_TIMEOUT) -> bool:
    """Abre a tela antiga de um relatorio e espera o formulario dele ficar pronto.

    As URLs do Sienge so mudam depois do '#': trocar de relatorio nao recarrega a pagina, o Sienge
    troca o iframe do formulario. O iframe da tela anterior e marcado antes de navegar, para nunca
    ser confundido com o novo. A folga de 6 s so comeca a contar com o formulario na tela: numa
    maquina lenta, a pausa fixa de antes podia acabar antes de a tela existir. Mesma URL da tela
    atual: recarrega, para o formulario vir limpo.
    """
    driver.switch_to.default_content()
    driver.execute_script(
        "const quadro = document.getElementById(arguments[0]); if (quadro) quadro.setAttribute(arguments[1], '1');",
        IFRAME_DO_RELATORIO,
        _MARCA_IFRAME_ANTERIOR,
    )
    if str(driver.current_url or "").strip() == str(url or "").strip():
        driver.refresh()
    else:
        driver.get(url)
    inicio = time.monotonic()
    try:
        WebDriverWait(driver, timeout, poll_frequency=0.2).until(
            lambda current_driver: current_driver.execute_script(
                _FORMULARIO_PRONTO_JS, IFRAME_DO_RELATORIO, _MARCA_IFRAME_ANTERIOR
            )
        )
        pronta = True
        logger.info("Tela do relatorio pronta em %.1f s.", time.monotonic() - inicio)
    except TimeoutException:
        pronta = False
        logger.warning("A tela do relatorio nao ficou pronta em %s s; o executor segue mesmo assim.", timeout)
    time.sleep(PAUSA_APOS_TELA_PRONTA)
    return pronta


def aguardar_carregamento_da_pagina(driver, wait, timeout=DEFAULT_TIMEOUT):
    try:
        return WebDriverWait(driver, timeout).until(
            lambda _driver: _driver.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        logger.warning("A pagina nao terminou de carregar no tempo esperado.")
        return False


def fechar_janelas_extras(driver):
    """Fecha as abas web abertas pelo relatorio e volta para a aba do Sienge.

    Nunca toca em janela interna do Edge (edge://, devtools://...) e nunca usa a
    "janela atual" como referencia: depois de uma falha ela pode ser um dialogo.

    Chamar so depois de o download chegar (renomear_download): a janela "please_wait_frame" do
    Sienge e quem pede o arquivo, e fechada antes da resposta o download nunca comeca.
    """
    principal = janela_principal(driver)
    urls = _urls_das_janelas(driver)
    for handle in list(driver.window_handles):
        if handle == principal:
            continue
        url = _url_da_janela(driver, handle, urls)
        if url is None or _url_eh_interna(url):
            continue
        try:
            driver.switch_to.window(handle)
            driver.close()
            logger.info("Janela extra do relatorio fechada: %s", url or handle)
        except WebDriverException:
            logger.warning("Janela extra %s nao pode ser fechada; seguindo.", url or handle)
    voltar_para_janela_principal(driver)


def caminho_navegador(navegador: str = SELENIUM_BROWSER) -> str | None:
    """Executavel do navegador configurado em SELENIUM_BROWSER, se estiver instalado."""
    if navegador == "chrome":
        return _get_chrome_path()
    if navegador == "edge":
        return _get_edge_path()
    return None
