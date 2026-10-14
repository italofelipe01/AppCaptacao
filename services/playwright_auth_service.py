"""
Servico de autenticacao Sienge via Playwright.
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


LOGIN_URL = os.getenv("SIENGE_LOGIN_URL", "https://ebm.sienge.com.br/sienge/")
DEFAULT_TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_DEFAULT_TIMEOUT_MS", "20000"))
POST_LOGIN_WAIT_SECONDS = int(os.getenv("PLAYWRIGHT_POST_LOGIN_WAIT_SECONDS", "8"))
MICROSOFT_MFA_WAIT_SECONDS = int(os.getenv("PLAYWRIGHT_MICROSOFT_MFA_WAIT_SECONDS", "60"))
PLAYWRIGHT_BROWSER_ENGINE = os.getenv("PLAYWRIGHT_BROWSER_ENGINE", "chromium").strip().lower() or "chromium"
PLAYWRIGHT_CHANNEL = os.getenv("PLAYWRIGHT_BROWSER_CHANNEL", "").strip() or None
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "false").strip().lower() == "true"
PLAYWRIGHT_USE_PERSISTENT_CONTEXT = (
    os.getenv("PLAYWRIGHT_USE_PERSISTENT_CONTEXT", "false").strip().lower() == "true"
)
PLAYWRIGHT_USER_DATA_DIR = (
    os.getenv("PLAYWRIGHT_USER_DATA_DIR")
    or os.path.join(tempfile.gettempdir(), "appcaptacao_playwright_profile")
)


logger = logging.getLogger(__name__)


class PlaywrightSession:
    def __init__(self, playwright_instance, context, page):
        self._playwright = playwright_instance
        self.context = context
        self.page = page

    def close(self):
        try:
            self.context.close()
        finally:
            self._playwright.stop()

    def quit(self):
        self.close()


def autenticar_sienge_playwright(email, senha):
    if not str(email or "").strip() or not str(senha or ""):
        raise ValueError("Informe email e senha para autenticar no Sienge.")

    playwright_instance = sync_playwright().start()
    browser_launcher = _obter_browser_launcher(playwright_instance)
    context, page = _criar_contexto_autenticacao(browser_launcher)

    try:
        _fazer_login(page, email, senha)
        time.sleep(POST_LOGIN_WAIT_SECONDS)

        if not _sessao_sienge_ativa(page):
            raise RuntimeError("A autenticacao no Sienge nao foi concluida.")

        return PlaywrightSession(playwright_instance, context, page)
    except Exception:
        context.close()
        playwright_instance.stop()
        raise


def _obter_browser_launcher(playwright_instance):
    if PLAYWRIGHT_BROWSER_ENGINE == "firefox":
        return playwright_instance.firefox
    if PLAYWRIGHT_BROWSER_ENGINE == "webkit":
        return playwright_instance.webkit
    return playwright_instance.chromium


def _criar_contexto_autenticacao(browser_launcher):
    launch_kwargs = {
        "headless": PLAYWRIGHT_HEADLESS,
    }
    if PLAYWRIGHT_CHANNEL:
        launch_kwargs["channel"] = PLAYWRIGHT_CHANNEL

    if PLAYWRIGHT_USE_PERSISTENT_CONTEXT:
        user_data_dir = Path(PLAYWRIGHT_USER_DATA_DIR)
        user_data_dir.mkdir(parents=True, exist_ok=True)
        context = browser_launcher.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            viewport=None,
            args=["--start-maximized"],
            **launch_kwargs,
        )
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = context.pages[0] if context.pages else context.new_page()
        logger.info(
            "Playwright autenticando com contexto persistente | engine=%s | channel=%s",
            PLAYWRIGHT_BROWSER_ENGINE,
            PLAYWRIGHT_CHANNEL or "bundled",
        )
        return context, page

    browser = browser_launcher.launch(**launch_kwargs)
    context = browser.new_context(viewport=None)
    context.set_default_timeout(DEFAULT_TIMEOUT_MS)
    page = context.new_page()
    page.set_viewport_size({"width": 1440, "height": 900})
    logger.info(
        "Playwright autenticando com navegador de automacao limpo | engine=%s | channel=%s",
        PLAYWRIGHT_BROWSER_ENGINE,
        PLAYWRIGHT_CHANNEL or "bundled",
    )
    return context, page


def _fazer_login(page, email, senha):
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")

    _clicar_se_existir(page, "#btnEntrarComSiengeID", "botao Entrar com Sienge ID")

    _preencher_se_existir(page, "input[name='email']", email, "email inicial do Sienge ID")
    if not _preencher_se_existir(page, "input[name='email']", email, "email inicial do Sienge ID"):
        _preencher_se_existir(page, "input[name='username']", email, "username inicial do Sienge ID")

    _clicar_primeiro_disponivel(
        page,
        [
            "[data-testid='sign-in-v2-submit-button']",
            "button:has-text('Continuar')",
            "button:has-text('CONTINUAR')",
        ],
        "botao Continuar do Sienge ID",
    )

    if _preencher_se_existir(page, "input[name='loginfmt']", email, "email Microsoft"):
        _clicar_se_existir(page, "#idSIButton9", "botao avancar Microsoft")

    if _preencher_se_existir(page, "input[name='passwd']", senha, "senha Microsoft"):
        _clicar_se_existir(page, "#idSIButton9", "botao entrar Microsoft")
        logger.info(
            "Aguardando ate %s segundos para conclusao do token/autenticacao Microsoft.",
            MICROSOFT_MFA_WAIT_SECONDS,
        )
        time.sleep(MICROSOFT_MFA_WAIT_SECONDS)

    _clicar_se_existir(page, "#idBtn_Back", "botao Nao permanecer conectado")


def _clicar_primeiro_disponivel(page, seletores, descricao):
    for seletor in seletores:
        if _clicar_se_existir(page, seletor, descricao):
            return True
    return False


def _clicar_se_existir(page, seletor, descricao):
    locator = page.locator(seletor).first
    try:
        locator.wait_for(state="visible", timeout=5000)
        locator.click()
        return True
    except PlaywrightTimeoutError:
        logger.info("Elemento nao encontrado para %s | seletor=%s", descricao, seletor)
        return False


def _preencher_se_existir(page, seletor, valor, descricao):
    locator = page.locator(seletor).first
    try:
        locator.wait_for(state="visible", timeout=5000)
        locator.fill("")
        locator.fill(valor)
        return True
    except PlaywrightTimeoutError:
        logger.info("Campo nao encontrado para %s | seletor=%s", descricao, seletor)
        return False


def _sessao_sienge_ativa(page):
    url_atual = (page.url or "").strip().lower()
    if not url_atual or "sienge.com.br" not in url_atual:
        return False

    try:
        return page.locator("#btnEntrarComSiengeID").count() == 0
    except Exception:
        return True
