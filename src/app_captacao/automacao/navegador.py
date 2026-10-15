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
from pathlib import Path
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
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

    try:
        driver.execute_cdp_cmd(
            "Browser.setDownloadBehavior",
            {
                "behavior": "allow",
                "downloadPath": str(Path(DOWNLOAD_DIR).resolve()),
                "eventsEnabled": True,
            },
        )
    except Exception:
        logger.warning("Nao foi possivel configurar downloads via CDP no Edge anexado.")

    _posicionar_na_aba_web(driver)
    logger.info("Selenium anexado ao Edge normal existente na porta %s.", EDGE_DEBUG_PORT)
    return driver


def _posicionar_na_aba_web(driver):
    """Coloca o driver numa aba de pagina web, de preferencia a do Sienge, e maximiza.

    O navegador anexado tambem expoe dialogos internos como janelas: num Windows
    ligado ao Entra ID, o perfil novo do Edge entra sozinho na conta e abre
    edge://sync-confirmation-dialog/. Maximizar esse dialogo falha com
    "Browser window not found".
    """
    host_sienge = (urlsplit(LOGIN_URL).hostname or "").lower()
    aba_web = aba_sienge = None
    for handle in list(driver.window_handles):
        try:
            driver.switch_to.window(handle)
            url = str(driver.current_url or "").lower()
        except WebDriverException:
            continue
        if url.startswith(_PREFIXOS_PAGINA_INTERNA):
            continue
        aba_web = aba_web or handle
        if host_sienge and (urlsplit(url).hostname or "") == host_sienge:
            aba_sienge = handle
            break

    if aba_sienge or aba_web:
        driver.switch_to.window(aba_sienge or aba_web)
    else:
        driver.switch_to.new_window("tab")

    try:
        driver.maximize_window()
    except WebDriverException:
        logger.warning("Nao foi possivel maximizar a janela do navegador anexado; seguindo assim mesmo.")


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


def aguardar_carregamento_da_pagina(driver, wait, timeout=DEFAULT_TIMEOUT):
    try:
        return WebDriverWait(driver, timeout).until(
            lambda _driver: _driver.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        logger.warning("A pagina nao terminou de carregar no tempo esperado.")
        return False


def fechar_janelas_extras(driver):
    """Fecha as abas extras; dialogo interno do Edge (edge://...) que nao fecha e ignorado."""
    main = driver.current_window_handle
    for handle in list(driver.window_handles):
        if handle == main:
            continue
        try:
            driver.switch_to.window(handle)
            driver.close()
        except WebDriverException:
            logger.info("Janela extra %s nao pode ser fechada; seguindo.", handle)
    driver.switch_to.window(main)


def caminho_navegador(navegador: str = SELENIUM_BROWSER) -> str | None:
    """Executavel do navegador configurado em SELENIUM_BROWSER, se estiver instalado."""
    if navegador == "chrome":
        return _get_chrome_path()
    if navegador == "edge":
        return _get_edge_path()
    return None
