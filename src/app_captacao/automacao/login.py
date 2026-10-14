"""Login no Sienge: Sienge ID, SSO Microsoft e espera do MFA.

O login e sempre feito pelo fluxo automatico; a sessao salva nao e restaurada
(ver docs/DECISIONS.md). Login so conta como concluido quando a sessao fica
estavel no dominio do Sienge e sem controles de login na tela.
"""

from __future__ import annotations

import logging
import time

from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app_captacao.automacao import erros, sessao
from app_captacao.automacao.config import (
    DEFAULT_TIMEOUT,
    INTERACTIVE_LOGIN_TIMEOUT,
    LOGIN_URL,
    MICROSOFT_MFA_WAIT,
    SESSION_REUSE_ENABLED,
)

logger = logging.getLogger(__name__)


def fazer_login(driver, wait, email, senha):
    try:
        return _fazer_login_automatico(driver, wait, email, senha)
    except (
        WebDriverException,
        TimeoutException,
        NoSuchElementException,
        erros.InteractiveAuthenticationRequired,
    ) as exc:
        logger.warning(
            "O redirecionamento do SSO interrompeu o preenchimento automatico (%s). "
            "Aguardando autenticacao interativa na mesma janela do navegador por ate %s segundos.",
            type(exc).__name__,
            INTERACTIVE_LOGIN_TIMEOUT,
        )
        if _aguardar_autenticacao_interativa(driver, INTERACTIVE_LOGIN_TIMEOUT):
            logger.info("Autenticacao interativa concluida e validada no Sienge.")
            if SESSION_REUSE_ENABLED:
                sessao.salvar_sessao_sienge(driver, email)
            return
        raise RuntimeError(
            "A autenticacao do Sienge nao foi concluida. "
            "Conclua o login e o token na janela do Edge dentro do tempo informado."
        ) from exc


def _fazer_login_automatico(driver, wait, email, senha):
    # Replica o fluxo comprovado pelo BaixaPDFs. A unica diferenca fica na
    # criacao do driver, que neste sistema pode iniciar no Edge ou no Chrome.
    driver.get(LOGIN_URL)
    login_wait = WebDriverWait(driver, max(DEFAULT_TIMEOUT, 30))

    botao = login_wait.until(
        EC.element_to_be_clickable((By.ID, "btnEntrarComSiengeID"))
    )
    botao.click()

    campo_email = _aguardar_primeiro_elemento(
        driver,
        login_wait,
        [
            (By.NAME, "email"),
            (By.NAME, "username"),
        ],
        descricao="campo inicial de email do Sienge ID",
    )
    campo_email.clear()
    campo_email.send_keys(email)

    botao_continuar_locator = (
        By.XPATH,
        "//button[@data-testid='sign-in-v2-submit-button'] | "
        "//button[contains(normalize-space(.), 'Continuar') or "
        "contains(normalize-space(.), 'CONTINUAR')] | "
        "//button[@type='submit' and contains(normalize-space(.), 'Continuar')]",
    )
    login_wait.until(EC.presence_of_element_located(botao_continuar_locator))
    _clicar_elemento_com_fallback(
        driver,
        botao_continuar_locator,
        descricao="botao Continuar do Sienge ID",
    )

    try:
        botao_continuar = driver.find_element(*botao_continuar_locator)
        login_wait.until(EC.staleness_of(botao_continuar))
    except Exception:
        logger.debug("Botao Continuar nao saiu da pagina antes de continuar.")

    try:
        campo_autenticador_email = login_wait.until(
            EC.presence_of_element_located((By.NAME, "loginfmt"))
        )
        campo_autenticador_email.clear()
        campo_autenticador_email.send_keys(email)
        botao_microsoft_locator = (
            By.XPATH,
            "//input[@id='idSIButton9'] | "
            "//button[contains(normalize-space(.), 'Entrar') or "
            "contains(normalize-space(.), 'Continuar')]",
        )
        login_wait.until(EC.presence_of_element_located(botao_microsoft_locator))
        _clicar_elemento_com_fallback(
            driver,
            botao_microsoft_locator,
            descricao="botao de avancar da Microsoft",
        )
        login_wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//input[@type='password' or @name='passwd' or @name='password']")
            )
        )
    except (TimeoutException, NoSuchElementException):
        logger.info(
            "Tela Microsoft de login nao apareceu; continuando para o campo de senha."
        )

    campo_senha = _aguardar_primeiro_elemento(
        driver,
        login_wait,
        [
            (By.NAME, "passwd"),
            (By.NAME, "password"),
            (By.XPATH, "//input[@type='password']"),
        ],
        descricao="campo senha do Sienge/Microsoft",
    )
    campo_senha.clear()
    campo_senha.send_keys(senha)

    try:
        botao_entrar_locator = (By.ID, "idSIButton9")
        login_wait.until(EC.element_to_be_clickable(botao_entrar_locator))
        _clicar_elemento_com_fallback(
            driver,
            botao_entrar_locator,
            descricao="botao Entrar Microsoft",
        )
        logger.info("Botao Entrar Microsoft pressionado.")
    except (TimeoutException, NoSuchElementException, StaleElementReferenceException):
        logger.warning(
            "Botao Entrar Microsoft nao encontrado ou nao clicavel; tentando botao alternativo."
        )
        try:
            botao_login_locator = (
                By.XPATH,
                "//button[contains(normalize-space(.), 'Entrar') or "
                "contains(normalize-space(.), 'Login') or "
                "contains(normalize-space(.), 'Continuar')]",
            )
            login_wait.until(EC.presence_of_element_located(botao_login_locator))
            _clicar_elemento_com_fallback(
                driver,
                botao_login_locator,
                descricao="botao de login final alternativo",
            )
        except (TimeoutException, NoSuchElementException, StaleElementReferenceException):
            logger.info(
                "Botao de login final alternativo nao encontrado; enviando ENTER no campo de senha."
            )
            campo_senha.send_keys(Keys.ENTER)

    logger.info(
        "Aguardando ate %s segundos para conclusao do token/autenticacao Microsoft.",
        MICROSOFT_MFA_WAIT,
    )
    time.sleep(MICROSOFT_MFA_WAIT)

    try:
        botao_voltar = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "idBtn_Back"))
        )
        botao_voltar.click()
    except Exception:
        pass

    if not _aguardar_sessao_sienge_estavel(driver, timeout_seconds=15):
        raise erros.InteractiveAuthenticationRequired(
            "A autenticacao interativa nao foi concluida. Conclua o MFA na janela do navegador e tente novamente."
        )


def _aguardar_autenticacao_interativa(driver, timeout_seconds):
    logger.info(
        "Conclua o login e o token manualmente na janela do navegador. Tempo limite: %s segundos.",
        timeout_seconds,
    )
    return _aguardar_sessao_sienge_estavel(driver, timeout_seconds)


def _aguardar_sessao_sienge_estavel(driver, timeout_seconds, confirmacoes_necessarias=4):
    deadline = time.time() + timeout_seconds
    tentativas_sem_janela = 0
    confirmacoes = 0
    ultima_url = ""

    while time.time() < deadline:
        try:
            handles = list(driver.window_handles)
            if not handles:
                tentativas_sem_janela += 1
                if tentativas_sem_janela >= 3:
                    return False
            else:
                tentativas_sem_janela = 0
                try:
                    if driver.current_window_handle not in handles:
                        driver.switch_to.window(handles[-1])
                except WebDriverException:
                    driver.switch_to.window(handles[-1])

                if sessao.sessao_sienge_ativa(driver):
                    url_atual = str(driver.current_url or "").strip().lower()
                    confirmacoes = confirmacoes + 1 if url_atual == ultima_url else 1
                    ultima_url = url_atual
                    if confirmacoes >= confirmacoes_necessarias:
                        return True
                else:
                    confirmacoes = 0
                    ultima_url = ""
        except WebDriverException:
            # Trocas de renderer/frame sao esperadas durante o SSO Microsoft.
            tentativas_sem_janela += 1
            if tentativas_sem_janela >= 3:
                return False
            confirmacoes = 0
            ultima_url = ""

        time.sleep(2)

    return False


def _aguardar_primeiro_elemento(driver, wait, locators, descricao="elemento"):
    ultimo_erro = None

    for locator in locators:
        try:
            return wait.until(EC.presence_of_element_located(locator))
        except (TimeoutException, NoSuchElementException) as exc:
            ultimo_erro = exc
            logger.info("Locator %s nao encontrado para %s.", locator, descricao)

    if ultimo_erro:
        raise ultimo_erro

    raise TimeoutException(f"Nenhum locator informado para localizar {descricao}.")


def _clicar_elemento_com_fallback(driver, locator, descricao="elemento"):
    """Clica como o BaixaPDFs, tolerando rerenderizacao durante o SSO."""
    ultimo_erro = None

    for tentativa in range(1, 5):
        try:
            driver.find_element(*locator).click()
            return
        except Exception as exc:
            ultimo_erro = exc
            logger.warning(
                "Tentativa %s de clique falhou para %s: %s",
                tentativa,
                descricao,
                type(exc).__name__,
            )

        alternativas = (
            lambda elemento: driver.execute_script(
                "arguments[0].scrollIntoView(true); arguments[0].click();", elemento
            ),
            lambda elemento: elemento.send_keys(Keys.ENTER),
            lambda elemento: driver.execute_script(
                "var el = arguments[0]; var form = el.closest('form'); "
                "if (form) { form.submit(); } else { "
                "el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true})); }",
                elemento,
            ),
        )
        for clicar in alternativas:
            try:
                clicar(driver.find_element(*locator))
                return
            except Exception as exc:
                ultimo_erro = exc

        time.sleep(0.5)

    logger.error(
        "Nao foi possivel clicar em %s apos varias tentativas: %s",
        descricao,
        ultimo_erro,
    )
    raise ultimo_erro
