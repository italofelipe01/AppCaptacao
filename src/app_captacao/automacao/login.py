"""Login no Sienge: Sienge ID, SSO Microsoft e espera do MFA.

O login reconhece, a cada ciclo, qual tela esta aberta e age nela ate a sessao
ficar estavel no Sienge. As telas mudam conforme o estado do navegador e da
maquina (mapa em docs/processos/login_sienge.md):

- Sienge ID: formulario de e-mail ou "escolher conta" (e-mail lembrado no perfil
  do navegador ou sessao do Sienge ID ainda ativa);
- Microsoft: "escolha uma conta" (Windows ligado ao Entra ID), e-mail, senha,
  MFA e "continuar conectado?";
- Sienge: "usuario ja conectado" em outra sessao.

So elementos visiveis contam: as telas da Microsoft deixam campos ocultos de
e-mail e senha no HTML. A senha e enviada no maximo uma vez por login, para nao
bloquear a conta por tentativas repetidas. A sessao salva nao e restaurada
(ver docs/DECISIONS.md).
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from urllib.parse import urlsplit

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from app_captacao.automacao import erros, sessao
from app_captacao.automacao.config import (
    DEFAULT_TIMEOUT,
    INTERACTIVE_LOGIN_TIMEOUT,
    LOGIN_URL,
    MICROSOFT_MFA_WAIT,
    SESSION_REUSE_ENABLED,
)

logger = logging.getLogger(__name__)

TELA_SIENGE_ENTRAR = "sienge_entrar"
TELA_SIENGE_JA_CONECTADO = "sienge_ja_conectado"
TELA_SIENGE_LOGADO = "sienge_logado"
TELA_SIENGE_ID_ESCOLHER_CONTA = "sienge_id_escolher_conta"
TELA_SIENGE_ID_EMAIL = "sienge_id_email"
TELA_SIENGE_ID_SENHA = "sienge_id_senha"
TELA_SIENGE_ID_ERRO = "sienge_id_erro"
TELA_MS_ESCOLHER_CONTA = "microsoft_escolher_conta"
TELA_MS_EMAIL = "microsoft_email"
TELA_MS_SENHA = "microsoft_senha"
TELA_MS_MFA = "microsoft_mfa"
TELA_MS_CONTINUAR_CONECTADO = "microsoft_continuar_conectado"
TELA_MS_ERRO = "microsoft_erro"
TELA_CARREGANDO = "carregando"

_SIENGE_ENTRAR = (By.ID, "btnEntrarComSiengeID")
_SIENGE_PROSSEGUIR = (By.CSS_SELECTOR, "a[href*='removerUsuarioLogadoServlet?acao=S']")

_SID_PAGINA = (By.CSS_SELECTOR, "[data-testid='sign-in-v2-page-container']")
_SID_ESCOLHER_CONTA = (By.CSS_SELECTOR, "[data-testid='sign-in-v2-choose-account-container']")
_SID_USUARIO_ATUAL = (By.CSS_SELECTOR, "[data-testid='sign-in-v2-current-user-login']")
_SID_CONTA_LEMBRADA = (By.CSS_SELECTOR, "[data-testid='sign-in-v2-login-item-button']")
_SID_USAR_OUTRA_CONTA = (By.CSS_SELECTOR, "[data-testid='sign-in-v2-use-other-account-button']")
_SID_EMAIL = (By.CSS_SELECTOR, "input[name='email']")
_SID_SENHA = (By.CSS_SELECTOR, "input[name='password']")
_SID_CONTINUAR = (By.CSS_SELECTOR, "[data-testid='sign-in-v2-submit-button']")
_SID_ERRO = (By.CSS_SELECTOR, "[data-testid='sign-in-v2-error-alert']")

_MS_CONTAS = (By.ID, "tilesHolder")
_MS_CONTA = (By.CSS_SELECTOR, "#tilesHolder [data-test-id]")
_MS_OUTRA_CONTA = (By.ID, "otherTile")
_MS_EMAIL = (By.NAME, "loginfmt")
_MS_SENHA = (By.NAME, "passwd")
_MS_AVANCAR = (By.ID, "idSIButton9")
_MS_ERRO = (By.CSS_SELECTOR, "#usernameError, #passwordError")
_MS_MFA = (By.CSS_SELECTOR, "#idDiv_SAOTCAS_Title, #idRichContext_DisplaySign, #idDiv_SAOTCC_Title")
_MS_MFA_NUMERO = (By.ID, "idRichContext_DisplaySign")
_MS_CONTINUAR_CONECTADO = (By.ID, "KmsiCheckboxField")
_MS_NAO = (By.ID, "idBtn_Back")

_HOSTS_MICROSOFT = ("login.microsoftonline.com", "login.microsoft.com", "login.live.com")

# Quantas vezes a automacao age na mesma tela antes de desistir. A senha vai uma
# vez so: repetir uma senha recusada pode bloquear a conta no Entra ID.
_TENTATIVAS_POR_TELA = 3
_TENTATIVAS_SENHA = 1


def fazer_login(driver, wait, email, senha):
    try:
        return _fazer_login_automatico(driver, email, senha)
    except (WebDriverException, erros.InteractiveAuthenticationRequired) as exc:
        motivo = erros.mensagem_erro_usuario(exc, type(exc).__name__)
        logger.warning(
            "O login automatico nao foi concluido (%s). "
            "Aguardando autenticacao interativa na mesma janela do navegador por ate %s segundos.",
            motivo,
            INTERACTIVE_LOGIN_TIMEOUT,
        )
        if _aguardar_autenticacao_interativa(driver, INTERACTIVE_LOGIN_TIMEOUT):
            logger.info("Autenticacao interativa concluida e validada no Sienge.")
            if SESSION_REUSE_ENABLED:
                sessao.salvar_sessao_sienge(driver, email)
            return
        raise RuntimeError(
            f"A autenticacao do Sienge nao foi concluida: {motivo.rstrip('.')}. "
            "Conclua o login e o token na janela do Edge dentro do tempo informado."
        ) from exc


def _fazer_login_automatico(driver, email, senha):
    driver.get(LOGIN_URL)
    prazo_tela = max(DEFAULT_TIMEOUT, 30)
    prazo_total = time.time() + MICROSOFT_MFA_WAIT + 10 * prazo_tela
    tentativas = Counter()
    tela_anterior = None
    desde = time.time()

    while time.time() < prazo_total:
        _garantir_janela_ativa(driver)
        tela = identificar_tela(driver)
        if tela != tela_anterior:
            logger.info("Login Sienge: tela %s.", tela)
            tela_anterior, desde = tela, time.time()
            if tela == TELA_MS_MFA:
                _avisar_mfa(driver)

        if tela == TELA_SIENGE_LOGADO:
            if _aguardar_sessao_sienge_estavel(driver, prazo_tela):
                logger.info("Login concluido; sessao estavel no Sienge.")
                return
            continue

        if tela in (TELA_MS_ERRO, TELA_SIENGE_ID_ERRO):
            raise erros.InteractiveAuthenticationRequired(_mensagem_de_erro(driver, tela))

        acao = _ACOES.get(tela)
        if acao is None:
            limite = MICROSOFT_MFA_WAIT if tela == TELA_MS_MFA else prazo_tela
            if time.time() - desde > limite:
                raise erros.InteractiveAuthenticationRequired(
                    f"A tela de login '{tela}' nao avancou em {limite} segundos."
                )
            time.sleep(1)
            continue

        maximo = _TENTATIVAS_SENHA if tela in (TELA_MS_SENHA, TELA_SIENGE_ID_SENHA) else _TENTATIVAS_POR_TELA
        if tentativas[tela] >= maximo:
            raise erros.InteractiveAuthenticationRequired(
                f"A tela de login '{tela}' nao avancou apos {maximo} tentativa(s)."
            )
        tentativas[tela] += 1
        acao(driver, email, senha)
        _aguardar_saida_da_tela(driver, tela, prazo_tela)

    raise erros.InteractiveAuthenticationRequired("Tempo esgotado no login automatico do Sienge.")


def identificar_tela(driver):
    """Nome da tela de login aberta na janela atual (TELA_*)."""
    url = _url_atual(driver)
    host = (urlsplit(url).hostname or "").lower()

    if host in _HOSTS_MICROSOFT:
        if _visivel(driver, _MS_ERRO):
            return TELA_MS_ERRO
        if _visivel(driver, _MS_CONTAS):
            return TELA_MS_ESCOLHER_CONTA
        # Senha antes do e-mail: a tela de senha mantem o loginfmt oculto e vice-versa.
        if _visivel(driver, _MS_SENHA):
            return TELA_MS_SENHA
        if _visivel(driver, _MS_EMAIL):
            return TELA_MS_EMAIL
        if _visivel(driver, _MS_MFA):
            return TELA_MS_MFA
        if _visivel(driver, _MS_CONTINUAR_CONECTADO) or "/kmsi" in url.lower():
            return TELA_MS_CONTINUAR_CONECTADO
        return TELA_CARREGANDO

    if _existe(driver, _SID_PAGINA):
        if _visivel(driver, _SID_ERRO):
            return TELA_SIENGE_ID_ERRO
        if _visivel(driver, _SID_ESCOLHER_CONTA):
            return TELA_SIENGE_ID_ESCOLHER_CONTA
        if _visivel(driver, _SID_SENHA):
            return TELA_SIENGE_ID_SENHA
        if _visivel(driver, _SID_EMAIL):
            return TELA_SIENGE_ID_EMAIL
        return TELA_CARREGANDO

    if _visivel(driver, _SIENGE_PROSSEGUIR):
        return TELA_SIENGE_JA_CONECTADO
    if _visivel(driver, _SIENGE_ENTRAR):
        return TELA_SIENGE_ENTRAR
    if sessao.sessao_sienge_ativa(driver):
        return TELA_SIENGE_LOGADO
    return TELA_CARREGANDO


def _entrar_com_sienge_id(driver, email, senha):
    _clicar(driver, _primeiro_visivel(driver, _SIENGE_ENTRAR))


def _prosseguir_desconectando_sessao_anterior(driver, email, senha):
    logger.warning(
        "O usuario ja tinha uma sessao aberta no Sienge; ela sera encerrada para a automacao entrar."
    )
    _clicar(driver, _primeiro_visivel(driver, _SIENGE_PROSSEGUIR))


def _escolher_conta_sienge_id(driver, email, senha):
    conta = _visivel_com_texto(driver, _SID_USUARIO_ATUAL, email) or _visivel_com_texto(
        driver, _SID_CONTA_LEMBRADA, email
    )
    if conta is not None:
        logger.info("Sienge ID: usando a conta %s ja conhecida pelo navegador.", email)
        _clicar(driver, conta)
        return
    logger.info("Sienge ID: a conta %s nao esta na lista; usando outra conta.", email)
    _clicar(driver, _primeiro_visivel(driver, _SID_USAR_OUTRA_CONTA))


def _informar_email_sienge_id(driver, email, senha):
    _preencher_email(_primeiro_visivel(driver, _SID_EMAIL), email)
    _clicar(driver, _primeiro_visivel(driver, _SID_CONTINUAR))


def _informar_senha_sienge_id(driver, email, senha):
    _preencher_senha(_primeiro_visivel(driver, _SID_SENHA), senha)
    _clicar(driver, _primeiro_visivel(driver, _SID_CONTINUAR))


def _escolher_conta_microsoft(driver, email, senha):
    for conta in _visiveis(driver, _MS_CONTA):
        if _mesmo_email(conta.get_attribute("data-test-id"), email):
            logger.info("Microsoft: usando a conta %s da lista.", email)
            _clicar(driver, conta)
            return
    logger.info("Microsoft: a conta %s nao esta na lista; usando outra conta.", email)
    _clicar(driver, _primeiro_visivel(driver, _MS_OUTRA_CONTA))


def _informar_email_microsoft(driver, email, senha):
    campo = _primeiro_visivel(driver, _MS_EMAIL)
    _preencher_email(campo, email)
    _avancar_microsoft(driver, campo)


def _informar_senha_microsoft(driver, email, senha):
    campo = _primeiro_visivel(driver, _MS_SENHA)
    _preencher_senha(campo, senha)
    _avancar_microsoft(driver, campo)


def _recusar_continuar_conectado(driver, email, senha):
    _clicar(driver, _primeiro_visivel(driver, _MS_NAO))


_ACOES = {
    TELA_SIENGE_ENTRAR: _entrar_com_sienge_id,
    TELA_SIENGE_JA_CONECTADO: _prosseguir_desconectando_sessao_anterior,
    TELA_SIENGE_ID_ESCOLHER_CONTA: _escolher_conta_sienge_id,
    TELA_SIENGE_ID_EMAIL: _informar_email_sienge_id,
    TELA_SIENGE_ID_SENHA: _informar_senha_sienge_id,
    TELA_MS_ESCOLHER_CONTA: _escolher_conta_microsoft,
    TELA_MS_EMAIL: _informar_email_microsoft,
    TELA_MS_SENHA: _informar_senha_microsoft,
    TELA_MS_CONTINUAR_CONECTADO: _recusar_continuar_conectado,
}


def _avancar_microsoft(driver, campo):
    botao = _primeiro_visivel(driver, _MS_AVANCAR)
    if botao is not None:
        _clicar(driver, botao)
    else:
        campo.send_keys(Keys.ENTER)


def _avisar_mfa(driver):
    numero = ""
    elemento = _primeiro_visivel(driver, _MS_MFA_NUMERO)
    if elemento is not None:
        numero = (elemento.text or "").strip()
    logger.info(
        "Aguardando aprovacao do MFA no Microsoft Authenticator%s por ate %s segundos.",
        f" (numero {numero})" if numero else "",
        MICROSOFT_MFA_WAIT,
    )


def _mensagem_de_erro(driver, tela):
    seletor = _MS_ERRO if tela == TELA_MS_ERRO else _SID_ERRO
    elemento = _primeiro_visivel(driver, seletor)
    detalhe = " ".join(((elemento.text if elemento is not None else "") or "").split())
    origem = "A Microsoft" if tela == TELA_MS_ERRO else "O Sienge ID"
    return f"{origem} recusou o login{': ' + detalhe if detalhe else '.'}"


def _aguardar_saida_da_tela(driver, tela, timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        time.sleep(0.5)
        _garantir_janela_ativa(driver)
        if identificar_tela(driver) != tela:
            return True
    return False


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


def _garantir_janela_ativa(driver):
    try:
        handles = list(driver.window_handles)
        if handles and driver.current_window_handle not in handles:
            driver.switch_to.window(handles[-1])
    except WebDriverException:
        try:
            handles = list(driver.window_handles)
            if handles:
                driver.switch_to.window(handles[-1])
        except WebDriverException:
            pass


def _url_atual(driver):
    try:
        return str(driver.current_url or "")
    except WebDriverException:
        return ""


def _visiveis(driver, locator):
    try:
        return [elemento for elemento in driver.find_elements(*locator) if elemento.is_displayed()]
    except WebDriverException:
        return []


def _primeiro_visivel(driver, locator):
    elementos = _visiveis(driver, locator)
    return elementos[0] if elementos else None


def _visivel(driver, locator):
    return bool(_visiveis(driver, locator))


def _existe(driver, locator):
    try:
        return bool(driver.find_elements(*locator))
    except WebDriverException:
        return False


def _visivel_com_texto(driver, locator, email):
    for elemento in _visiveis(driver, locator):
        if str(email or "").strip().lower() in (elemento.text or "").lower():
            return elemento
    return None


def _mesmo_email(valor, email):
    return str(valor or "").strip().lower() == str(email or "").strip().lower()


def _preencher_email(campo, email):
    if _mesmo_email(campo.get_attribute("value"), email):
        return
    campo.clear()
    campo.send_keys(email)


def _preencher_senha(campo, senha):
    if not senha:
        raise erros.InteractiveAuthenticationRequired("A senha nao foi informada para a execucao.")
    campo.clear()
    campo.send_keys(senha)


def _clicar(driver, elemento):
    if elemento is None:
        raise erros.InteractiveAuthenticationRequired("O botao esperado na tela de login sumiu.")
    try:
        elemento.click()
    except WebDriverException:
        # Sobreposicao ou rerenderizacao durante o SSO: o clique via JS nao depende do ponto da tela.
        driver.execute_script("arguments[0].click();", elemento)
