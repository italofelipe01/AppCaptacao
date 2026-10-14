"""Persistencia da sessao do Sienge (cookies e storage) cifrada com DPAPI.

A sessao e salva apos login interativo, mas nao e restaurada no fluxo atual.
"""

from __future__ import annotations

import logging
import os
import pickle
import tempfile
import time
from hashlib import md5

from selenium.webdriver.common.by import By

from app_captacao.automacao.config import LOGIN_URL
from app_captacao.core.config.dpapi import decrypt_bytes_for_current_user, encrypt_bytes_for_current_user
from app_captacao.core.config.environment import ensure_config_dir, get_sienge_session_store_dir

logger = logging.getLogger(__name__)


def _obter_caminho_sessao(email):
    email_normalizado = str(email or "").strip().lower()
    hash_email = md5(email_normalizado.encode("utf-8")).hexdigest()
    if os.name == "nt":
        return str(ensure_config_dir(get_sienge_session_store_dir()) / f"sienge_session_{hash_email}.bin")
    return os.path.join(tempfile.gettempdir(), f"sienge_session_{hash_email}.pkl")


def salvar_sessao_sienge(driver, email):
    try:
        caminho_sessao = _obter_caminho_sessao(email)
        cookies = driver.get_cookies()
        local_storage = driver.execute_script(
            """
            var items = {};
            for (var i = 0; i < localStorage.length; i++) {
                var key = localStorage.key(i);
                items[key] = localStorage.getItem(key);
            }
            return items;
            """
        )
        session_storage = driver.execute_script(
            """
            var items = {};
            for (var i = 0; i < sessionStorage.length; i++) {
                var key = sessionStorage.key(i);
                items[key] = sessionStorage.getItem(key);
            }
            return items;
            """
        )

        payload_sessao = pickle.dumps(
            {
                "cookies": cookies,
                "local_storage": local_storage,
                "session_storage": session_storage,
            }
        )
        if os.name == "nt":
            payload_sessao = encrypt_bytes_for_current_user(payload_sessao)

        with open(caminho_sessao, "wb") as arquivo_sessao:
            arquivo_sessao.write(payload_sessao)

        logger.info(
            "Sessao Sienge salva para %s em %s com %s cookies.",
            email,
            caminho_sessao,
            len(cookies),
        )
        return True
    except Exception:
        logger.exception("Nao foi possivel salvar a sessao Sienge de %s.", email)
        return False


def restaurar_sessao_sienge(driver, email):
    caminho_sessao = _obter_caminho_sessao(email)
    if not os.path.exists(caminho_sessao):
        return False

    try:
        with open(caminho_sessao, "rb") as arquivo_sessao:
            payload_sessao = arquivo_sessao.read()
        if os.name == "nt":
            payload_sessao = decrypt_bytes_for_current_user(payload_sessao)
        sessao = pickle.loads(payload_sessao)

        driver.get(LOGIN_URL)
        time.sleep(3)
        driver.delete_all_cookies()

        for cookie in sessao.get("cookies", []):
            try:
                cookie_limpo = {
                    chave: valor
                    for chave, valor in cookie.items()
                    if chave in {"name", "value", "domain", "path", "secure", "httpOnly", "expiry"}
                }
                if "domain" not in cookie_limpo or not cookie_limpo["domain"]:
                    cookie_limpo["domain"] = ".sienge.com.br"
                driver.add_cookie(cookie_limpo)
            except Exception:
                logger.debug("Falha ao restaurar cookie %s.", cookie.get("name"))

        for chave, valor in sessao.get("local_storage", {}).items():
            try:
                driver.execute_script("window.localStorage.setItem(arguments[0], arguments[1]);", chave, valor)
            except Exception:
                logger.debug("Falha ao restaurar localStorage[%s].", chave)

        for chave, valor in sessao.get("session_storage", {}).items():
            try:
                driver.execute_script("window.sessionStorage.setItem(arguments[0], arguments[1]);", chave, valor)
            except Exception:
                logger.debug("Falha ao restaurar sessionStorage[%s].", chave)

        driver.refresh()
        time.sleep(6)

        if sessao_sienge_ativa(driver):
            return True

        logger.info("Sessao restaurada para %s expirou; login interativo sera necessario.", email)
        return False
    except Exception:
        logger.exception("Nao foi possivel restaurar a sessao Sienge de %s.", email)
        return False


def sessao_sienge_ativa(driver):
    try:
        if driver.current_window_handle not in driver.window_handles:
            return False
        url_atual = str(driver.current_url or "").strip().lower()
        estado_documento = driver.execute_script("return document.readyState")
    except Exception:
        return False

    if not url_atual or url_atual in {"about:blank", "edge://newtab/", "chrome://newtab/"}:
        return False

    if estado_documento != "complete":
        return False

    if any(token in url_atual for token in ("login.microsoftonline.com", "/oauth", "/signin")):
        return False

    autenticacao_locators = (
        (By.ID, "btnEntrarComSiengeID"),
        (By.NAME, "loginfmt"),
        (By.NAME, "passwd"),
        (By.NAME, "email"),
        (By.NAME, "username"),
    )
    for locator in autenticacao_locators:
        try:
            if driver.find_elements(*locator):
                return False
        except Exception:
            return False

    if "sienge.com.br" not in url_atual:
        return False

    return True
