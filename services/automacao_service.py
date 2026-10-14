"""
Serviço de Automação - Execução de Relatórios via Selenium
============================================================

Módulo responsável pela automação de navegação no sistema Sienge
para execução de relatórios automatizados. Utiliza Selenium WebDriver
para controlar o navegador configurado.

Autor: Equipe de Desenvolvimento
Versão: 1.0.0
Data: Abril 2026
"""

import logging
import os
import pickle
import re
import shutil
import socket
import subprocess
import tempfile
import time
import traceback
import ctypes
from datetime import date, datetime
from hashlib import md5
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from services.report_modules import executar_relatorio_dedicado as executar_modulo_relatorio
from services.relatorio_action_service import (
    eh_botao_automatico,
    obter_executor_botao,
    obter_executor_relatorio,
)
from app_core.app_config import (
    decrypt_bytes_for_current_user,
    encrypt_bytes_for_current_user,
    ensure_config_dir,
    get_sienge_session_store_dir,
)

# ============================================================
# CONFIGURAÇÕES DE CONEXÃO E TIMEOUTS
# ============================================================

# URL base do sistema Sienge
LOGIN_URL = os.getenv("SIENGE_LOGIN_URL", "https://ebm.sienge.com.br/sienge/")

# Timeout padrão para esperas explícitas (segundos)
DEFAULT_TIMEOUT = int(os.getenv("SELENIUM_DEFAULT_TIMEOUT", "20"))

# Tempo de espera após executar relatório (segundos)
DEFAULT_REPORT_WAIT = max(int(os.getenv("SELENIUM_REPORT_WAIT_SECONDS", "5")), 5)

# Timeout para download de arquivos (segundos)
DOWNLOAD_WAIT_TIMEOUT = int(os.getenv("SELENIUM_DOWNLOAD_WAIT_TIMEOUT_SECONDS", "600"))
DOWNLOAD_TEMP_EXTENSIONS = {".crdownload", ".tmp", ".part", ".download"}
DOWNLOAD_STABLE_CHECK_INTERVAL = 0.75
DOWNLOAD_STABLE_CYCLES_REQUIRED = int(os.getenv("SELENIUM_DOWNLOAD_STABLE_CYCLES", "3"))
DOWNLOAD_QUIET_PERIOD_SECONDS = float(os.getenv("SELENIUM_DOWNLOAD_QUIET_PERIOD_SECONDS", "2.5"))

# Tempo de espera após login (segundos)
POST_LOGIN_WAIT = int(os.getenv("SELENIUM_POST_LOGIN_WAIT_SECONDS", "8"))

# Tempo para concluir o desafio MFA/token da Microsoft (segundos)
MICROSOFT_MFA_WAIT = int(os.getenv("SELENIUM_MICROSOFT_MFA_WAIT_SECONDS", "60"))

# Tempo de espera interação com campos (segundos)
FIELD_INTERACTION_WAIT = float(os.getenv("SELENIUM_FIELD_INTERACTION_WAIT_SECONDS", "1.5"))

# Número de tentativas para preencher campos
FIELD_RETRY_COUNT = int(os.getenv("SELENIUM_FIELD_RETRY_COUNT", "3"))

# Habilitar reutilização de sessão do navegador
SESSION_REUSE_ENABLED = os.getenv("SIENGE_SESSION_REUSE_ENABLED", "true").strip().lower() == "true"

# Navegador Selenium preferencial para a automação
SELENIUM_BROWSER = os.getenv("SELENIUM_BROWSER", "edge").strip().lower()
ATTACH_NORMAL_CHROME = os.getenv("SELENIUM_ATTACH_NORMAL_CHROME", "false").strip().lower() == "true"
CHROME_DEBUG_HOST = os.getenv("SELENIUM_CHROME_DEBUG_HOST", "127.0.0.1").strip() or "127.0.0.1"
CHROME_DEBUG_PORT = int(os.getenv("SELENIUM_CHROME_DEBUG_PORT", "9222"))
CHROME_USER_DATA_DIR = os.getenv("CHROME_USER_DATA_DIR", "").strip()
CHROME_PROFILE_DIRECTORY = os.getenv("CHROME_PROFILE_DIRECTORY", "").strip()
FORCAR_LOGIN_INTERATIVO = os.getenv("SIENGE_FORCE_INTERACTIVE_LOGIN", "false").strip().lower() == "true"

# Reutilizacao opcional do perfil real do Edge para fluxos de SSO/Microsoft.
EDGE_USE_PROFILE = os.getenv("EDGE_USE_PROFILE", "true").strip().lower() == "true"
EDGE_USER_DATA_DIR = (
    os.getenv("EDGE_USER_DATA_DIR")
    or os.path.join(os.getenv("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data")
)
EDGE_PROFILE_DIRECTORY = os.getenv("EDGE_PROFILE_DIRECTORY", "Default").strip() or "Default"

# Diretório para downloads (padrão: pasta Downloads do usuário)
DOWNLOAD_DIR = (
    os.getenv("SELENIUM_DOWNLOAD_DIR")
    or str(Path.home() / "Downloads" / "Automação CAP")
)

# ============================================================
# IDENTIFICADORES DE CAMPOS DO SIENGE
# ============================================================

# Campos fixos para filtros de relatório
CAMPO_EMPRESA = "filter.empresa.cdEmpresaView"
CAMPO_EMPREENDIMENTO = "filter.empreend.cdEmpreendView"

# Palavras-chave para identificar campos de consulta
IDENTIFICADORES_CAMPO_CONSULTA = (
    "empresa",
    "centrocusto",
    "centro_custo",
    "centro-custo",
    "custo",
    ".cdempresa",
    ".cdcentrocusto",
    ".cdcustocentro",
    "cdempresa",
    "cdcentrocusto",
)

# Índice do iframe padrão para consultas
CONSULTA_IFRAME_PADRAO = 0

# Configuração de logging
logger = logging.getLogger(__name__)
DEBUG_ARTIFACTS_ENABLED = os.getenv("SELENIUM_DEBUG_ARTIFACTS", "false").strip().lower() == "true"

# ============================================================
# MAPA DE LOCATORS SELENIUM
# ============================================================

# Mapeamento de tipos de localizadores para constantes Selenium
BY_MAP = {
    "ID": By.ID,
    "NAME": By.NAME,
    "XPATH": By.XPATH,
    "CSS": By.CSS_SELECTOR,
    "CSS_SELECTOR": By.CSS_SELECTOR,
    "CLASS_NAME": By.CLASS_NAME,
    "TAG_NAME": By.TAG_NAME,
    "LINK_TEXT": By.LINK_TEXT,
    "PARTIAL_LINK_TEXT": By.PARTIAL_LINK_TEXT,
}

# ============================================================
# AÇÕES QUE EXIGEM VALOR
# ============================================================

# Conjunto de ações que requerem preenchimento de valor
ACOES_QUE_EXIGEM_VALOR = {
    "fill",
    "fill_tab",
    "type",
    "type_tab",
    "write",
    "write_tab",
    "preencher",
    "preencher_tab",
    "send_keys",
}


class DownloadProcessingError(RuntimeError):
    def __init__(self, etapa, mensagem):
        super().__init__(mensagem)
        self.etapa = etapa


def acao_exige_valor(acao):
    """
    Verifica se uma ação requer valor para execução.
    
    Args:
        acao: Nome da ação a verificar
    
    Returns:
        bool: True se a ação requer valor, False caso contrário
    """
    acao_normalizada = normalizar_acao(acao)
    if not acao_normalizada:
        return True
    return acao_normalizada in ACOES_QUE_EXIGEM_VALOR


def executar_relatorio(email, senha, relatorio_config, driver=None, sessao_autenticada=False):
    driver_gerenciado = driver is None

    try:
        driver = driver or _criar_driver()
        wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
        if not sessao_autenticada:
            _fazer_login(driver, wait, email, senha)
            time.sleep(POST_LOGIN_WAIT)

        arquivos = _executar_relatorio_no_driver(driver, wait, relatorio_config)
        stable = _aguardar_pasta_download_estabilizar()
        if not stable:
            logger.warning(
                "A pasta de downloads nao estabilizou apos a execucao do relatorio %s. Aguardando mais %s segundos.",
                relatorio_config.get("id"),
                DEFAULT_REPORT_WAIT,
            )
            time.sleep(DEFAULT_REPORT_WAIT)
            _aguardar_pasta_download_estabilizar()
        item = _montar_item_resultado(relatorio_config, "baixado", arquivos=arquivos)
        return {
            "tipo_execucao": "relatorio",
            "itens": [item],
            "sucessos": [item],
            "falhas": [],
            "quantidade_relatorios": 1,
            "quantidade_baixados": 1,
            "quantidade_nao_baixados": 0,
            "resumo": "1 relatorio baixado; 0 nao baixados.",
        }
    except Exception as exc:
        logger.exception("Falha ao executar o relatorio %s.", relatorio_config.get("nome", ""))
        item = _montar_item_resultado(
            relatorio_config,
            "nao_baixado",
            mensagem=str(exc) or "Falha durante a execucao do relatorio.",
            etapa=getattr(exc, "etapa", "execucao"),
        )
        return {
            "tipo_execucao": "relatorio",
            "itens": [item],
            "sucessos": [],
            "falhas": [item],
            "quantidade_relatorios": 1,
            "quantidade_baixados": 0,
            "quantidade_nao_baixados": 1,
            "mensagem": item["mensagem"],
            "resumo": "0 relatorios baixados; 1 nao baixado.",
        }
    finally:
        if driver_gerenciado and driver and os.getenv("SELENIUM_KEEP_BROWSER_OPEN", "true").strip().lower() != "true":
            driver.quit()


def executar_relatorios_em_sequencia(email, senha, relatorios_config, on_report_event=None):
    if not relatorios_config:
        return {
            "quantidade_relatorios": 0,
            "quantidade_baixados": 0,
            "quantidade_nao_baixados": 0,
            "itens": [],
            "sucessos": [],
            "falhas": [],
            "resumo": "Nenhum relatorio para executar.",
        }

    driver = None
    resultado_execucao = {
        "quantidade_relatorios": len(relatorios_config),
        "quantidade_baixados": 0,
        "quantidade_nao_baixados": 0,
        "itens": [],
        "sucessos": [],
        "falhas": [],
    }
    try:
        try:
            driver = _criar_driver()
            wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
            _fazer_login(driver, wait, email, senha)
        except Exception as exc:
            logger.exception("O navegador ou a autenticacao nao foi concluido; os relatorios serao ignorados.")
            for relatorio_config in relatorios_config:
                item = _montar_item_resultado(
                    relatorio_config,
                    "ignorado",
                    mensagem=f"Navegador ou autenticacao nao concluido: {exc}",
                    etapa="autenticacao",
                )
                resultado_execucao["itens"].append(item)
                resultado_execucao["falhas"].append(item)
            resultado_execucao["quantidade_nao_baixados"] = len(relatorios_config)
            resultado_execucao["resumo"] = (
                f"0 relatorios baixados; {len(relatorios_config)} nao baixados."
            )
            return resultado_execucao
        time.sleep(POST_LOGIN_WAIT)

        total = len(relatorios_config)
        for indice, relatorio_config in enumerate(relatorios_config, start=1):
            logger.info(
                "Executando relatorio %s/%s na mesma sessao | id=%s | nome=%s",
                indice,
                total,
                relatorio_config.get("id"),
                relatorio_config.get("nome", ""),
            )
            try:
                if on_report_event:
                    on_report_event(
                        "processando",
                        relatorio_config,
                        {
                            "indice": indice,
                            "total": total,
                        },
                    )
                arquivos = _executar_relatorio_no_driver(driver, wait, relatorio_config)
                eh_ultimo = indice == total
                item = _montar_item_resultado(
                    relatorio_config,
                    "baixado",
                    arquivos=arquivos,
                    indice=indice,
                    total=total,
                )
                item["eh_ultimo"] = eh_ultimo
                resultado_execucao["itens"].append(item)
                resultado_execucao["sucessos"].append(item)
                if on_report_event:
                    on_report_event(
                        "sucesso",
                        relatorio_config,
                        {
                            "indice": indice,
                            "total": total,
                            "eh_ultimo": eh_ultimo,
                        },
                    )
                if not eh_ultimo:
                    stable = _aguardar_pasta_download_estabilizar()
                    if not stable:
                        logger.warning(
                            "A pasta de downloads nao estabilizou apos o relatorio %s. Aguardando mais %s segundos.",
                            relatorio_config.get("id"),
                            DEFAULT_REPORT_WAIT,
                        )
                        time.sleep(DEFAULT_REPORT_WAIT)
                        _aguardar_pasta_download_estabilizar()
                    logger.info(
                        "Aguardando %s segundos antes de iniciar o proximo relatorio.",
                        DEFAULT_REPORT_WAIT,
                    )
                    time.sleep(DEFAULT_REPORT_WAIT)
                else:
                    logger.info("Ultimo relatorio da sequencia. Nao aguarda finalizacao.")
            except Exception as exc:
                detalhe_erro = _montar_item_resultado(
                    relatorio_config,
                    "nao_baixado",
                    mensagem=str(exc) or "Erro na execucao da automacao para o relatorio.",
                    etapa=getattr(exc, "etapa", "execucao"),
                    indice=indice,
                    total=total,
                )
                resultado_execucao["itens"].append(detalhe_erro)
                resultado_execucao["falhas"].append(detalhe_erro)
                logger.exception(
                    "Erro na execucao da automacao da operacao para o relatorio %s.",
                    relatorio_config.get("id"),
                )
                if on_report_event:
                    on_report_event("erro", relatorio_config, detalhe_erro)
    finally:
        if driver and os.getenv("SELENIUM_KEEP_BROWSER_OPEN", "true").strip().lower() != "true":
            driver.quit()
    resultado_execucao["quantidade_baixados"] = len(resultado_execucao["sucessos"])
    resultado_execucao["quantidade_nao_baixados"] = len(resultado_execucao["falhas"])
    resultado_execucao["resumo"] = (
        f"{resultado_execucao['quantidade_baixados']} relatorio(s) baixado(s); "
        f"{resultado_execucao['quantidade_nao_baixados']} nao baixado(s)."
    )
    return resultado_execucao


def _montar_item_resultado(
    relatorio_config,
    estado,
    arquivos=None,
    mensagem="",
    etapa="",
    indice=None,
    total=None,
):
    arquivos = [str(item) for item in (arquivos or []) if str(item or "").strip()]
    return {
        "indice": indice,
        "total": total,
        "relatorio_id": relatorio_config.get("id") or relatorio_config.get("id_relatorio"),
        "relatorio_nome": relatorio_config.get("nome", ""),
        "operacao_nome": relatorio_config.get("operacao_nome", ""),
        "estado": estado,
        "mensagem": mensagem,
        "etapa": etapa,
        "caminho_final": arquivos[-1] if arquivos else "",
        "arquivos": arquivos,
    }


def autenticar_sienge(email, senha):
    """
    Abre o navegador, autentica no Sienge e devolve o driver autenticado.

    Args:
        email: Email do usuario no Sienge
        senha: Senha do usuario no Sienge
    Returns:
        selenium.webdriver.Chrome: Driver autenticado
    """
    if not str(email or "").strip() or not str(senha or ""):
        raise ValueError("Informe email e senha para autenticar no Sienge.")

    driver = _criar_driver()
    try:
        wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
        _fazer_login(driver, wait, email, senha)
        time.sleep(POST_LOGIN_WAIT)

        if not _sessao_sienge_ativa(driver):
            raise RuntimeError("A autenticacao no Sienge nao foi concluida.")

        return driver
    except Exception:
        driver.quit()
        raise


def _executar_relatorio_no_driver(driver, wait, relatorio_config):
    relatorio_config["_arquivos_finais"] = []
    relatorio_url = (relatorio_config.get("url") or "").strip()
    if not relatorio_url:
        raise ValueError(
            f"O relatorio '{relatorio_config.get('nome', '')}' nao possui UrlRelatorio cadastrada."
        )

    driver.switch_to.default_content()
    _fechar_janelas_extras(driver)

    logger.info(
        "Abrindo relatorio '%s' na URL %s",
        relatorio_config.get("nome", ""),
        relatorio_url,
    )
    driver.get(relatorio_url)
    _aguardar_carregamento_da_pagina(driver, wait)

    url_normalizada = relatorio_url.lower()
    if "/common/page/3012" in url_normalizada or relatorio_config.get("id") == 7:
        executor_relatorio = "extrato_cliente_historico"
    else:
        executor_relatorio = obter_executor_relatorio(
            relatorio_config.get("nome", ""),
            relatorio_config.get("id_relatorio_operacao"),
            relatorio_config.get("id"),
            relatorio_url,
        )
    if not executor_relatorio:
        raise ValueError(
            "Relatorio sem modulo dedicado configurado: "
            f"id={relatorio_config.get('id')} | "
            f"id_relatorio_operacao={relatorio_config.get('id_relatorio_operacao')} | "
            f"nome={relatorio_config.get('nome', '')}"
        )

    if executor_relatorio != "extrato_saldo_devedor_presente":
        time.sleep(6)

    _executar_relatorio_dedicado(driver, wait, relatorio_config, executor_relatorio)
    _aguardar_carregamento_da_pagina(driver, wait)
    arquivos = list(dict.fromkeys(relatorio_config.get("_arquivos_finais", [])))
    if not arquivos:
        raise DownloadProcessingError(
            "download",
            "O executor terminou, mas nenhum arquivo novo foi confirmado no destino.",
        )
    return arquivos


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
    options.add_experimental_option("detach", True)
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
        handles = list(driver.window_handles)
        if handles:
            driver.switch_to.window(handles[-1])
        driver.get(LOGIN_URL)
        driver.maximize_window()
        logger.info(
            "Driver anexado ao Chrome e posicionado na ultima aba com a URL de login do Sienge."
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

    caminho_perfil = Path(user_data_dir)
    if not caminho_perfil.exists():
        logger.warning(
            "Diretorio do perfil do Edge nao encontrado: %s. Edge iniciara sem perfil local.",
            caminho_perfil,
        )
        return options

    options.add_argument(f"--user-data-dir={caminho_perfil}")
    if profile_directory:
        options.add_argument(f"--profile-directory={profile_directory}")

    logger.info(
        "Edge iniciara com perfil local | user_data_dir=%s | profile=%s",
        caminho_perfil,
        profile_directory or "Default",
    )
    return options


def _criar_driver_edge():
    options = _configurar_browser_options(webdriver.EdgeOptions())
    options = _configurar_edge_profile(options)
    return webdriver.Edge(options=options)


def _criar_driver_chrome():
    if ATTACH_NORMAL_CHROME:
        return _anexar_ao_chrome_normal()

    options = _configurar_browser_options(webdriver.ChromeOptions())
    return webdriver.Chrome(options=options)


def _criar_driver():
    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

    browser = SELENIUM_BROWSER or "edge"
    if browser == "chrome":
        logger.info("Inicializando Selenium com Chrome.")
        return _criar_driver_chrome()

    if browser == "edge":
        try:
            logger.info("Inicializando Selenium com Edge.")
            return _criar_driver_edge()
        except Exception as exc:
            logger.warning(
                "Falha ao inicializar Edge (%s). Tentando Chrome como fallback.",
                type(exc).__name__,
            )
            return _criar_driver_chrome()

    logger.warning(
        "Navegador Selenium '%s' nao suportado. Usando Edge como padrao.",
        browser,
    )
    try:
        return _criar_driver_edge()
    except Exception:
        logger.warning("Falha no Edge padrao. Tentando Chrome como fallback.")
        return _criar_driver_chrome()


def _executar_relatorio_dedicado(driver, wait, relatorio_config, executor_relatorio):
    logger.info(
        "Executando relatorio '%s' com executor dedicado '%s'.",
        relatorio_config.get("nome", ""),
        executor_relatorio,
    )
    executar_modulo_relatorio(
        executor_relatorio,
        driver,
        wait,
        relatorio_config,
        {
            "logger": logger,
            "by_map": BY_MAP,
            "default_report_wait": DEFAULT_REPORT_WAIT,
            "campo_empresa": CAMPO_EMPRESA,
            "campo_empreendimento": CAMPO_EMPREENDIMENTO,
            "normalizar_valor": _normalizar_valor_automacao,
            "preencher_campo_antigo": _preencher_campo_legado,
            "preencher_autocomplete_enter": _preencher_autocomplete_com_enter,
            "marcar_inicio_download": _marcar_inicio_download,
            "renomear_download": _renomear_download_relatorio,
            "download_dir": DOWNLOAD_DIR,
            "sanitizar_nome_arquivo": _sanitizar_nome_arquivo,
            "copiar_download_para_sharepoint": _copiar_download_para_sharepoint,
            "montar_caminho_download_unico": _montar_caminho_download_unico,
            "capture_debug_snapshot": lambda nome, driver_ref=driver: _capture_debug_snapshot(driver_ref, nome),
        },
    )


def _aguardar_carregamento_da_pagina(driver, wait, timeout=DEFAULT_TIMEOUT):
    try:
        return WebDriverWait(driver, timeout).until(
            lambda _driver: _driver.execute_script("return document.readyState") == "complete"
        )
    except TimeoutException:
        logger.warning("A pagina nao terminou de carregar no tempo esperado.")
        return False


def _fazer_login(driver, wait, email, senha):
    if not FORCAR_LOGIN_INTERATIVO and SESSION_REUSE_ENABLED and _restaurar_sessao_sienge(driver, email):
        logger.info("Sessao reaproveitada com sucesso para %s.", email)
        return

    driver.get(LOGIN_URL)
    time.sleep(5)

    botao = _aguardar_primeiro_elemento(
        driver,
        wait,
        [
            (By.ID, "btnEntrarComSiengeID"),
            (By.XPATH, "//*[@id='btnEntrarComSiengeID']"),
        ],
        descricao="botao Entrar com Sienge ID",
    )
    try:
        botao.click()
    except Exception:
        driver.execute_script("arguments[0].click();", botao)
    time.sleep(5)

    campo_email = _aguardar_primeiro_elemento(
        driver,
        wait,
        [
            (By.NAME, "email"),
            (By.NAME, "username"),
        ],
        descricao="campo inicial de email do Sienge ID",
    )
    campo_email.send_keys(email)
    time.sleep(5)

    botao_continuar = _aguardar_primeiro_elemento(
        driver,
        wait,
        [
            (By.CSS_SELECTOR, "[data-testid='sign-in-v2-submit-button']"),
            (By.XPATH, "//button[contains(normalize-space(.), 'Continuar')]"),
            (By.XPATH, "//button[contains(normalize-space(.), 'CONTINUAR')]"),
            (By.XPATH, "//button[@type='submit' and contains(normalize-space(.), 'Continuar')]"),
        ],
        descricao="botao Continuar do Sienge ID",
    )
    botao_continuar.click()
    time.sleep(5)

    try:
        campo_autenticador_email = wait.until(
            EC.presence_of_element_located((By.NAME, "loginfmt"))
        )
        campo_autenticador_email.send_keys(email)
        time.sleep(5)
        driver.find_element(By.ID, "idSIButton9").click()
        time.sleep(5)
    except (TimeoutException, NoSuchElementException):
        pass

    try:
        campo_senha = wait.until(EC.presence_of_element_located((By.NAME, "passwd")))
        campo_senha.send_keys(senha)
        time.sleep(5)
        driver.find_element(By.ID, "idSIButton9").click()
        logger.info(
            "Aguardando ate %s segundos para conclusao do token/autenticacao Microsoft.",
            MICROSOFT_MFA_WAIT,
        )
        time.sleep(MICROSOFT_MFA_WAIT)
    except (TimeoutException, NoSuchElementException):
        pass

    try:
        driver.find_element(By.ID, "idBtn_Back").click()
        time.sleep(6)
    except NoSuchElementException:
        pass

    if not _sessao_sienge_ativa(driver):
        raise RuntimeError(
            "A autenticacao interativa nao foi concluida. Conclua o MFA na janela do navegador e tente novamente."
        )

    if SESSION_REUSE_ENABLED:
        _salvar_sessao_sienge(driver, email)


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


def _montar_lotes_execucao(filtros):
    if not filtros:
        return []

    valores_expandiveis = []
    for filtro in filtros:
        valor = filtro.get("valor")
        if isinstance(valor, list):
            partes = [str(item).strip() for item in valor if str(item).strip()]
        else:
            partes = [parte.strip() for parte in str(valor or "").split(",") if parte.strip()]

        if len(partes) > 1:
            valores_expandiveis.append(len(partes))

    total_lotes = max(valores_expandiveis, default=1)
    lotes = []

    for indice in range(total_lotes):
        lote = []
        for filtro in filtros:
            clone = dict(filtro)
            valor = filtro.get("valor")

            if isinstance(valor, list):
                partes = [str(item).strip() for item in valor if str(item).strip()]
            else:
                partes = [parte.strip() for parte in str(valor or "").split(",") if parte.strip()]

            if len(partes) > 1:
                if len(partes) != total_lotes:
                    raise ValueError(
                        f"O filtro '{filtro.get('nome')}' possui quantidade de valores diferente dos demais."
                    )
                clone["valor"] = partes[indice]
            elif len(partes) == 1:
                clone["valor"] = partes[0]
            else:
                clone["valor"] = ""

            lote.append(clone)

        lotes.append(_ordenar_filtros_execucao(lote))

    return lotes


def _executar_filtro(driver, wait, filtro, nome_relatorio=""):
    if _deve_ignorar_campo_historico(filtro):
        logger.info(
            "Ignorando filtro historico removido | nome=%s | campo=%s",
            filtro.get("nome", ""),
            filtro.get("campo_identificador", ""),
        )
        return

    acao = normalizar_acao(filtro.get("acao"))
    if not acao:
        acao = "fill_tab"

    if acao == "noop":
        return

    elemento = None
    if acao not in {"enter", "submit", "close_windows"}:
        elemento = _localizar_elemento(driver, wait, filtro)

    valor = _normalizar_valor_automacao(filtro)
    logger.info(
        "Executando filtro '%s' | iframe=%s | tipo=%s | campo=%s | acao=%s | valor=%s",
        filtro.get("nome", ""),
        filtro.get("iframe_index"),
        filtro.get("tipo_campo"),
        filtro.get("campo_identificador"),
        acao,
        valor,
    )

    executor_botao = obter_executor_botao(nome_relatorio, filtro)
    if executor_botao:
        _executar_botao_automatico(driver, wait, filtro, executor_botao)
        return

    if acao in {"fill", "type", "write", "preencher"}:
        _preencher(driver, elemento, valor, usar_tab=False)
        return

    if acao in {"fill_tab", "type_tab", "write_tab", "preencher_tab", "send_keys"}:
        if _usa_fluxo_extrato_cliente_historico(nome_relatorio):
            _preencher_campo_estilo_antigo(driver, wait, filtro, valor)
            return
        if _eh_campo_consulta_sienge(filtro):
            _preencher_campo_consulta_sienge(driver, wait, filtro, valor)
            return
        _preencher(driver, elemento, valor, usar_tab=True)
        return

    if acao == "click":
        _clicar_elemento(driver, wait, elemento)
        driver.switch_to.default_content()
        return

    if acao == "clear":
        driver.find_element(*elemento).clear()
        driver.switch_to.default_content()
        return

    if acao == "enter":
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        return

    if acao == "submit":
        if elemento:
            driver.find_element(*elemento).submit()
        else:
            ActionChains(driver).send_keys(Keys.ENTER).perform()
        driver.switch_to.default_content()
        return

    if acao.startswith("wait"):
        _, _, tempo = acao.partition(":")
        time.sleep(int(tempo or DEFAULT_REPORT_WAIT))
        return

    if acao == "close_windows":
        _fechar_janelas_extras(driver)
        return

    raise ValueError(f"Acao de filtro nao suportada: {filtro.get('acao')}")


def _usa_fluxo_legado_empresa_empreendimento(filtros):
    identificadores = {
        (filtro.get("campo_identificador") or "").strip()
        for filtro in filtros
    }
    return (
        CAMPO_EMPRESA in identificadores
        and CAMPO_EMPREENDIMENTO in identificadores
    )


def _executar_fluxo_legado_empresa_empreendimento(driver, wait, lotes, nome_relatorio=""):
    for indice_lote, lote in enumerate(lotes, start=1):
        logger.info("Executando lote legado %s/%s.", indice_lote, len(lotes))

        if _usa_fluxo_extrato_cliente_historico(nome_relatorio):
            _executar_fluxo_extrato_cliente_historico(driver, wait, lote, nome_relatorio)
            continue

        filtros_acao = []
        houve_acao_envio = False

        for filtro in _ordenar_filtros_execucao(lote, nome_relatorio):
            acao = normalizar_acao(filtro.get("acao"))
            campo_identificador = (filtro.get("campo_identificador") or "").strip()

            if acao in {"enter", "submit", "close_windows"} or acao.startswith("wait"):
                filtros_acao.append(filtro)
                continue

            if campo_identificador in {CAMPO_EMPRESA, CAMPO_EMPREENDIMENTO}:
                _preencher_campo_legado(driver, wait, filtro)
                continue

            _executar_filtro(driver, wait, filtro, nome_relatorio)

        for filtro in filtros_acao:
            acao = normalizar_acao(filtro.get("acao"))
            if acao in {"enter", "submit"}:
                houve_acao_envio = True
            _executar_filtro(driver, wait, filtro, nome_relatorio)

        if not houve_acao_envio:
            logger.info(
                "Nenhuma acao de envio cadastrada no lote %s. Disparando ENTER no estilo legado.",
                indice_lote,
            )
            ActionChains(driver).send_keys(Keys.ENTER).perform()

        time.sleep(DEFAULT_REPORT_WAIT)
        _fechar_janelas_extras(driver)


def _executar_fluxo_extrato_cliente_historico(driver, wait, lote, nome_relatorio):
    filtros_ordenados = _ordenar_filtros_execucao(lote, nome_relatorio)
    filtros_acao = []

    for filtro in filtros_ordenados:
        acao = normalizar_acao(filtro.get("acao"))
        campo_identificador = (filtro.get("campo_identificador") or "").strip()

        if acao in {"enter", "submit", "close_windows"} or acao.startswith("wait"):
            filtros_acao.append(filtro)
            continue

        if campo_identificador == "filter.dtCorrecao":
            _executar_filtro(driver, wait, filtro, nome_relatorio)
            logger.info(
                "Fluxo extratoclientehistorico finalizado em dtCorrecao; interrompendo antes de qualquer novo TAB."
            )
            return

        if campo_identificador in {CAMPO_EMPRESA, CAMPO_EMPREENDIMENTO}:
            _preencher_campo_legado(driver, wait, filtro)
            continue

        _executar_filtro(driver, wait, filtro, nome_relatorio)

    for filtro in filtros_acao:
        _executar_filtro(driver, wait, filtro, nome_relatorio)


def _preencher_campo_legado(driver, wait, filtro):
    iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
    driver.switch_to.frame(iframe)

    tipo_campo = (filtro.get("tipo_campo") or "ID").upper()
    campo_identificador = (filtro.get("campo_identificador") or "").strip()
    by = BY_MAP.get(tipo_campo, By.ID)
    valor = _normalizar_valor_automacao(filtro)

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


def _eh_campo_consulta_sienge(filtro):
    nome = (filtro.get("nome") or "").strip().lower().replace(" ", "")
    campo_identificador = (filtro.get("campo_identificador") or "").strip().lower().replace(" ", "")

    return any(
        termo in nome or termo in campo_identificador
        for termo in IDENTIFICADORES_CAMPO_CONSULTA
    )


def _ordenar_filtros_execucao(filtros, nome_relatorio=""):
    return sorted(
        filtros,
        key=lambda filtro: (
            _prioridade_filtro_execucao(filtro, nome_relatorio),
            int(filtro.get("id") or 0),
        ),
    )


def _prioridade_filtro_execucao(filtro, nome_relatorio=""):
    nome = (filtro.get("nome") or "").strip().lower()
    campo_identificador = (filtro.get("campo_identificador") or "").strip().lower()
    acao = normalizar_acao(filtro.get("acao"))
    tipo_campo_valor = (filtro.get("tipo_campo_valor") or "").strip().upper()

    if _usa_fluxo_extrato_cliente_historico(nome_relatorio):
        if "vencimento inicio" in nome or "dtvenctoinicio" in campo_identificador:
            return 10

        if "vencimento fim" in nome or "dtvenctofim" in campo_identificador:
            return 20

        if "empresa" in nome or "empresa" in campo_identificador:
            return 30

        if (
            "empreendimento" in nome
            or "centro de custo" in nome
            or "centrocusto" in nome.replace(" ", "")
            or "empreend" in campo_identificador
            or "centrocusto" in campo_identificador.replace(" ", "")
        ):
            return 40

        if "correcao" in nome or "correção" in nome or "dtcorrecao" in campo_identificador:
            return 50

        if _eh_acao_envio(acao) or tipo_campo_valor == "CLICK":
            return 90

    if tipo_campo_valor == "CLICK":
        return 90

    if "empresa" in nome or "empresa" in campo_identificador:
        return 10

    if "vencimento inicio" in nome or "dtvenctoinicio" in campo_identificador:
        return 20

    if "vencimento fim" in nome or "dtvenctofim" in campo_identificador:
        return 30

    if (
        "empreendimento" in nome
        or "centro de custo" in nome
        or "centrocusto" in nome.replace(" ", "")
        or "empreend" in campo_identificador
        or "centrocusto" in campo_identificador.replace(" ", "")
    ):
        return 40

    if (
        "correcao" in nome
        or "correção" in nome
        or "historico" in nome
        or "dtcorrecao" in campo_identificador
        or "dthistorico" in campo_identificador
    ):
        return 50

    if _eh_acao_envio(acao) or _eh_botao_visualizar(nome, campo_identificador):
        return 90

    return 60


def _eh_acao_envio(acao):
    return acao in {"enter", "submit", "click"}


def _eh_botao_visualizar(nome, campo_identificador):
    return "visualizar" in nome or "visualizar" in campo_identificador


def _usa_fluxo_extrato_cliente_historico(nome_relatorio):
    nome_relatorio_normalizado = " ".join(str(nome_relatorio or "").strip().lower().split())
    return "extratoclientehistorico" in nome_relatorio_normalizado


def _deve_ignorar_campo_historico(filtro):
    nome = (filtro.get("nome") or "").strip().lower()
    campo_identificador = (filtro.get("campo_identificador") or "").strip().lower()
    return campo_identificador == "dthistorico" or "historico" in nome


def _preencher_campo_estilo_antigo(driver, wait, filtro, valor):
    campo_identificador = (filtro.get("campo_identificador") or "").strip()
    iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
    driver.switch_to.frame(iframe)

    tipo_campo = (filtro.get("tipo_campo") or "ID").upper()
    by = BY_MAP.get(tipo_campo, By.ID)
    valor_texto = str(valor or "")

    logger.info(
        "Preenchimento estilo antigo | nome=%s | tipo=%s | campo=%s | valor=%s",
        filtro.get("nome", ""),
        tipo_campo,
        campo_identificador,
        valor_texto,
    )

    try:
        campo = driver.find_element(by, campo_identificador)
        campo.clear()
        time.sleep(1)
        if campo_identificador == "filter.dtCorrecao":
            campo.click()
            time.sleep(0.3)
            campo.send_keys(Keys.CONTROL, "a")
            time.sleep(0.2)
            campo.send_keys(Keys.DELETE)
            time.sleep(0.2)
            _copiar_texto_para_area_transferencia(valor_texto)
            campo.send_keys(Keys.CONTROL, "v")
            time.sleep(0.5)
            valor_final = (campo.get_attribute("value") or "").strip()
            logger.info("dtCorrecao apos colagem: '%s'.", valor_final)
            campo.send_keys(Keys.ENTER)
            time.sleep(FIELD_INTERACTION_WAIT)
            driver.switch_to.default_content()
            _pressionar_tabs_consecutivos(driver, 12)
            ActionChains(driver).send_keys(Keys.ENTER).perform()
            logger.info("ENTER adicional disparado apos 12 TABs posteriores ao dtCorrecao.")
        else:
            campo.send_keys(valor_texto, Keys.TAB)
            time.sleep(1)
        if campo_identificador != "filter.dtCorrecao":
            valor_final = (campo.get_attribute("value") or "").strip()
        logger.info(
            "Preenchimento estilo antigo concluido | campo=%s | valor_final=%s",
            campo_identificador,
            valor_final if campo_identificador != "filter.dtCorrecao" else valor_texto,
        )
    finally:
        driver.switch_to.default_content()
        if campo_identificador == "filter.dtCorrecao":
            time.sleep(DEFAULT_REPORT_WAIT)
        else:
            time.sleep(1)


def _preencher_campo_consulta_sienge(driver, wait, filtro, valor):
    tipo_campo = (filtro.get("tipo_campo") or "ID").upper()
    campo_identificador = (filtro.get("campo_identificador") or "").strip()
    by = BY_MAP.get(tipo_campo, By.ID)
    valor_texto = str(valor or "")

    wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
    time.sleep(1)

    frames = driver.find_elements(By.TAG_NAME, "iframe")
    indices_tentativa = []
    iframe_preferencial = filtro.get("iframe_index")

    try:
        if iframe_preferencial not in (None, ""):
            indices_tentativa.append(int(iframe_preferencial))
    except (TypeError, ValueError):
        pass

    if CONSULTA_IFRAME_PADRAO not in indices_tentativa and CONSULTA_IFRAME_PADRAO < len(frames):
        indices_tentativa.insert(0, CONSULTA_IFRAME_PADRAO)

    indices_tentativa.extend(
        indice for indice in range(len(frames)) if indice not in indices_tentativa
    )

    ultimo_erro = None
    for indice in indices_tentativa:
        driver.switch_to.default_content()
        try:
            driver.switch_to.frame(frames[indice])
            campo = wait.until(EC.presence_of_element_located((by, campo_identificador)))
            valor_final = _executar_preenchimento_campo_consulta(campo, valor_texto)
            logger.info(
                "Preenchimento campo consulta | nome=%s | iframe=%s | campo=%s | valor_enviado=%s | valor_final=%s",
                filtro.get("nome", ""),
                indice,
                campo_identificador,
                valor_texto,
                valor_final,
            )

            if valor_texto and not valor_final:
                logger.warning(
                    "Campo consulta %s permaneceu vazio no iframe %s.",
                    campo_identificador,
                    indice,
                )
            else:
                driver.switch_to.default_content()
                return
        except (
            ElementNotInteractableException,
            NoSuchElementException,
            StaleElementReferenceException,
            TimeoutException,
            IndexError,
        ) as exc:
            ultimo_erro = exc
            logger.warning(
                "Falha ao preencher campo consulta %s no iframe %s.",
                campo_identificador,
                indice,
            )
        finally:
            driver.switch_to.default_content()

    if ultimo_erro:
        raise ultimo_erro


def _executar_preenchimento_campo_consulta(campo, valor_texto):
    campo.click()
    time.sleep(0.5)
    campo.clear()
    time.sleep(1)
    campo.send_keys(valor_texto, Keys.TAB)
    time.sleep(1.5)

    valor_final = (campo.get_attribute("value") or "").strip()
    if valor_final:
        return valor_final

    # Segunda tentativa mais agressiva para campos lookup do Sienge.
    campo.click()
    time.sleep(0.5)
    campo.send_keys(Keys.CONTROL, "a")
    time.sleep(0.2)
    campo.send_keys(Keys.DELETE)
    time.sleep(0.5)
    campo.send_keys(valor_texto)
    time.sleep(1)
    campo.send_keys(Keys.TAB)
    time.sleep(1)

    valor_final = (campo.get_attribute("value") or "").strip()
    if valor_final:
        return valor_final

    campo.send_keys(Keys.ENTER)
    time.sleep(1)
    return (campo.get_attribute("value") or "").strip()


def _preencher_autocomplete_com_enter(
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


def _localizar_elemento(driver, wait, filtro):
    driver.switch_to.default_content()
    _alternar_iframe(driver, wait, filtro.get("iframe_index"))

    tipo_campo = (filtro.get("tipo_campo") or "ID").upper()
    campo_identificador = filtro.get("campo_identificador")
    by = BY_MAP.get(tipo_campo)

    if not by:
        raise ValueError(f"TipoCampo nao suportado: {tipo_campo}")

    locator = (by, campo_identificador)
    try:
        wait.until(EC.presence_of_element_located(locator))
    except TimeoutException:
        frames = driver.find_elements(By.TAG_NAME, "iframe")
        logger.error(
            "Campo nao localizado | iframe_index=%s | total_iframes=%s | tipo=%s | campo=%s",
            filtro.get("iframe_index"),
            len(frames),
            tipo_campo,
            campo_identificador,
        )
        raise
    return locator


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


def _preencher(driver, locator, valor, usar_tab):
    ultimo_erro = None
    valor_texto = str(valor or "")

    for tentativa in range(1, FIELD_RETRY_COUNT + 1):
        try:
            WebDriverWait(driver, DEFAULT_TIMEOUT).until(EC.element_to_be_clickable(locator))
            elemento = driver.find_element(*locator)
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
                elemento,
            )
            time.sleep(0.3)
            elemento.click()
            time.sleep(FIELD_INTERACTION_WAIT)

            if usar_tab:
                try:
                    elemento.clear()
                except Exception:
                    driver.execute_script("arguments[0].value = '';", elemento)
                time.sleep(0.3)

                elemento.send_keys(valor_texto)
                time.sleep(FIELD_INTERACTION_WAIT)
                valor_preenchido = (elemento.get_attribute("value") or "").strip()

                if valor_texto and not valor_preenchido:
                    logger.warning(
                        "Campo %s permaneceu vazio apos send_keys. Aplicando fallback por JavaScript.",
                        locator,
                    )
                    driver.execute_script(
                        """
                        const element = arguments[0];
                        const value = arguments[1];
                        const setter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype,
                            'value'
                        ).set;
                        setter.call(element, value);
                        element.dispatchEvent(new Event('input', { bubbles: true }));
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                        """,
                        elemento,
                        valor_texto,
                    )
                    time.sleep(FIELD_INTERACTION_WAIT)
                    valor_preenchido = (elemento.get_attribute("value") or "").strip()

                elemento.send_keys(Keys.TAB)
                time.sleep(FIELD_INTERACTION_WAIT)
                valor_final = (elemento.get_attribute("value") or "").strip()
                logger.info("Campo %s preenchido com valor final '%s'.", locator, valor_final)
                driver.switch_to.default_content()
                return

            try:
                elemento.clear()
            except Exception:
                driver.execute_script("arguments[0].value = '';", elemento)
            time.sleep(0.3)
            elemento.send_keys(valor_texto)
            time.sleep(FIELD_INTERACTION_WAIT)
            valor_final = (elemento.get_attribute("value") or "").strip()
            logger.info("Campo %s preenchido com valor final '%s'.", locator, valor_final)
            driver.switch_to.default_content()
            return
        except (
            ElementNotInteractableException,
            NoSuchElementException,
            StaleElementReferenceException,
        ) as exc:
            ultimo_erro = exc
            logger.warning(
                "Falha ao preencher campo %s na tentativa %s/%s.",
                locator,
                tentativa,
                FIELD_RETRY_COUNT,
            )
            driver.switch_to.default_content()
            time.sleep(FIELD_INTERACTION_WAIT)
            continue

    raise ultimo_erro


def _clicar_elemento(driver, wait, locator):
    ultimo_erro = None

    for tentativa in range(1, FIELD_RETRY_COUNT + 1):
        try:
            wait.until(EC.presence_of_element_located(locator))
            wait.until(EC.element_to_be_clickable(locator))
            elemento = driver.find_element(*locator)
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
                elemento,
            )
            time.sleep(0.5)

            try:
                elemento.click()
            except Exception:
                try:
                    ActionChains(driver).move_to_element(elemento).click().perform()
                except Exception:
                    driver.execute_script("arguments[0].click();", elemento)

            time.sleep(FIELD_INTERACTION_WAIT)
            return
        except (
            ElementNotInteractableException,
            NoSuchElementException,
            StaleElementReferenceException,
            TimeoutException,
        ) as exc:
            ultimo_erro = exc
            logger.warning(
                "Falha ao clicar no elemento %s na tentativa %s/%s.",
                locator,
                tentativa,
                FIELD_RETRY_COUNT,
            )
            driver.switch_to.default_content()
            time.sleep(FIELD_INTERACTION_WAIT)
            _alternar_iframe(driver, wait, 0)

    raise ultimo_erro


def _executar_botao_automatico(driver, wait, filtro, executor_botao):
    logger.info(
        "Executando botao automatico '%s' com executor '%s'.",
        filtro.get("nome", ""),
        executor_botao,
    )

    if executor_botao == "press_enter":
        _pressionar_enter_global(driver)
        return

    if executor_botao == "submit_button":
        _submeter_botao(driver, wait, filtro)
        return

    raise ValueError(f"Executor de botao nao suportado: {executor_botao}")


def _submeter_botao(driver, wait, filtro):
    elemento = _localizar_elemento(driver, wait, filtro)
    ultimo_erro = None

    for tentativa in range(1, FIELD_RETRY_COUNT + 1):
        try:
            wait.until(EC.presence_of_element_located(elemento))
            botao = driver.find_element(*elemento)
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
                botao,
            )
            time.sleep(0.5)
            try:
                formulario = botao.find_element(By.XPATH, "./ancestor::form[1]")
                formulario.submit()
                logger.info(
                    "Botao %s submetido pelo formulario pai.",
                    filtro.get("campo_identificador"),
                )
            except NoSuchElementException:
                botao.send_keys(Keys.ENTER)
                logger.info(
                    "Botao %s submetido via ENTER.",
                    filtro.get("campo_identificador"),
                )
            time.sleep(FIELD_INTERACTION_WAIT)
            driver.switch_to.default_content()
            return
        except (
            ElementNotInteractableException,
            NoSuchElementException,
            StaleElementReferenceException,
            TimeoutException,
        ) as exc:
            ultimo_erro = exc
            logger.warning(
                "Falha ao submeter botao %s na tentativa %s/%s.",
                filtro.get("campo_identificador"),
                tentativa,
                FIELD_RETRY_COUNT,
            )
            try:
                botao = driver.find_element(*elemento)
                driver.execute_script(
                    """
                    const button = arguments[0];
                    const form = button.closest('form');
                    if (form) {
                        form.submit();
                    } else {
                        button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                    }
                    """,
                    botao,
                )
                logger.info(
                    "Botao %s submetido por fallback de formulario.",
                    filtro.get("campo_identificador"),
                )
                time.sleep(FIELD_INTERACTION_WAIT)
                driver.switch_to.default_content()
                return
            except Exception:
                driver.switch_to.default_content()
                _alternar_iframe(driver, wait, filtro.get("iframe_index"))
                time.sleep(FIELD_INTERACTION_WAIT)

    raise ultimo_erro


def _pressionar_enter_global(driver):
    driver.switch_to.default_content()
    time.sleep(0.5)
    ActionChains(driver).send_keys(Keys.ENTER).perform()
    logger.info("ENTER global disparado para concluir o filtro automatico.")
    time.sleep(FIELD_INTERACTION_WAIT)


def _normalizar_valor_automacao(filtro):
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


def _obter_caminho_sessao(email):
    email_normalizado = str(email or "").strip().lower()
    hash_email = md5(email_normalizado.encode("utf-8")).hexdigest()
    if os.name == "nt":
        return str(ensure_config_dir(get_sienge_session_store_dir()) / f"sienge_session_{hash_email}.bin")
    return os.path.join(tempfile.gettempdir(), f"sienge_session_{hash_email}.pkl")


def _salvar_sessao_sienge(driver, email):
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


def _restaurar_sessao_sienge(driver, email):
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

        if _sessao_sienge_ativa(driver):
            return True

        logger.info("Sessao restaurada para %s expirou; login interativo sera necessario.", email)
        return False
    except Exception:
        logger.exception("Nao foi possivel restaurar a sessao Sienge de %s.", email)
        return False


def _sessao_sienge_ativa(driver):
    try:
        url_atual = str(driver.current_url or "").strip().lower()
    except Exception:
        url_atual = ""

    if not url_atual or url_atual in {"about:blank", "edge://newtab/", "chrome://newtab/"}:
        return False

    try:
        driver.find_element(By.ID, "btnEntrarComSiengeID")
        return False
    except NoSuchElementException:
        pass

    if "sienge.com.br" not in url_atual:
        return False

    return True


def _fechar_janelas_extras(driver):
    main = driver.current_window_handle
    for handle in list(driver.window_handles):
        if handle == main:
            continue
        driver.switch_to.window(handle)
        driver.close()
    driver.switch_to.window(main)


def _marcar_inicio_download():
    pasta = Path(DOWNLOAD_DIR)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivos_antes = {}
    for arquivo in pasta.iterdir():
        if not arquivo.is_file():
            continue
        try:
            stat = arquivo.stat()
            arquivos_antes[str(arquivo.resolve())] = (stat.st_size, stat.st_mtime_ns)
        except OSError:
            continue
    return {"inicio_ns": time.time_ns(), "arquivos_antes": arquivos_antes}


def _renomear_download_relatorio(relatorio_config, empresa_id="", inicio_download=None):
    inicio_download = inicio_download or _marcar_inicio_download()
    arquivo = _aguardar_arquivo_download(inicio_download)
    if not arquivo:
        logger.warning(
            "Nenhum download novo encontrado para renomear | relatorio=%s | empresa=%s | pasta=%s",
            relatorio_config.get("nome", ""),
            empresa_id,
            DOWNLOAD_DIR,
        )
        raise DownloadProcessingError(
            "download",
            f"Nenhum arquivo novo foi concluido em '{DOWNLOAD_DIR}'.",
        )

    nome_relatorio = _sanitizar_nome_arquivo(relatorio_config.get("nome") or "relatorio")
    empresa = _sanitizar_nome_arquivo(str(empresa_id or "sem_empresa"))
    data_atual = datetime.now().strftime("%Y-%m-%d")
    destino = _montar_caminho_download_unico(
        arquivo.parent,
        f"{nome_relatorio}_{empresa}_{data_atual}",
        arquivo.suffix,
    )

    try:
        arquivo.rename(destino)
        if not destino.exists() or destino.stat().st_size <= 0:
            raise OSError("O arquivo renomeado nao foi confirmado no disco.")
        logger.info("Download renomeado | origem=%s | destino=%s", arquivo, destino)
    except OSError as exc:
        logger.exception("Nao foi possivel renomear o download %s.", arquivo)
        raise DownloadProcessingError("renomeacao", f"Falha ao renomear o arquivo: {exc}") from exc

    caminho_final = str(destino)
    if str(relatorio_config.get("sharepoint_link", "") or "").strip():
        caminho_final = _copiar_download_para_sharepoint(
            relatorio_config,
            destino,
            registrar_resultado=False,
        )
    relatorio_config.setdefault("_arquivos_finais", []).append(caminho_final)
    return caminho_final


def _aguardar_arquivo_download(inicio_download):
    pasta = Path(DOWNLOAD_DIR)
    pasta.mkdir(parents=True, exist_ok=True)
    prazo = time.time() + DOWNLOAD_WAIT_TIMEOUT
    estabilidade_por_arquivo = {}

    if isinstance(inicio_download, dict):
        inicio_ns = int(inicio_download.get("inicio_ns") or 0)
        arquivos_antes = inicio_download.get("arquivos_antes") or {}
    else:
        inicio_ns = int(float(inicio_download or 0) * 1_000_000_000)
        arquivos_antes = {}

    def arquivo_novo_ou_alterado(arquivo, stat):
        assinatura_anterior = arquivos_antes.get(str(arquivo.resolve()))
        if assinatura_anterior is None:
            return stat.st_mtime_ns >= inicio_ns
        return (stat.st_size, stat.st_mtime_ns) != tuple(assinatura_anterior) and stat.st_mtime_ns >= inicio_ns

    while time.time() <= prazo:
        downloads_em_andamento = []
        candidatos = []
        for arquivo in pasta.iterdir():
            if not arquivo.is_file():
                continue
            try:
                stat = arquivo.stat()
            except OSError:
                continue
            if not arquivo_novo_ou_alterado(arquivo, stat):
                continue
            if arquivo.suffix.lower() in DOWNLOAD_TEMP_EXTENSIONS:
                downloads_em_andamento.append(arquivo)
            else:
                candidatos.append(arquivo)

        if candidatos and not downloads_em_andamento:
            candidato = max(candidatos, key=lambda item: item.stat().st_mtime)
            tamanho_atual = candidato.stat().st_size
            if tamanho_atual <= 0:
                estabilidade_por_arquivo[candidato] = (tamanho_atual, 0)
            else:
                tamanho_anterior, ciclos_estaveis = estabilidade_por_arquivo.get(candidato, (None, 0))
                if tamanho_anterior == tamanho_atual:
                    ciclos_estaveis += 1
                else:
                    ciclos_estaveis = 1
                estabilidade_por_arquivo[candidato] = (tamanho_atual, ciclos_estaveis)
            if (
                tamanho_atual > 0
                and estabilidade_por_arquivo.get(candidato, (None, 0))[1] >= DOWNLOAD_STABLE_CYCLES_REQUIRED
            ):
                return candidato

        time.sleep(DOWNLOAD_STABLE_CHECK_INTERVAL)

    return ""


def _aguardar_pasta_download_estabilizar(timeout=DOWNLOAD_WAIT_TIMEOUT):
    pasta = Path(DOWNLOAD_DIR)
    prazo = time.time() + timeout

    while time.time() <= prazo:
        agora = time.time()
        downloads_em_andamento = []
        atividade_recente = []

        for arquivo in pasta.iterdir():
            if not arquivo.is_file():
                continue
            try:
                stat = arquivo.stat()
            except OSError:
                continue

            if arquivo.suffix.lower() in DOWNLOAD_TEMP_EXTENSIONS:
                downloads_em_andamento.append(arquivo)
                continue

            if stat.st_mtime >= agora - DOWNLOAD_QUIET_PERIOD_SECONDS:
                atividade_recente.append(arquivo)

        if not downloads_em_andamento and not atividade_recente:
            return True

        time.sleep(DOWNLOAD_STABLE_CHECK_INTERVAL)

    logger.warning(
        "A pasta de downloads nao estabilizou no tempo esperado | pasta=%s | timeout=%ss",
        DOWNLOAD_DIR,
        timeout,
    )
    return False


def _montar_caminho_download_unico(pasta, nome_base, extensao):
    destino = pasta / f"{nome_base}{extensao}"
    contador = 2

    while destino.exists():
        destino = pasta / f"{nome_base}_{contador}{extensao}"
        contador += 1

    return destino


def _capture_debug_snapshot(driver, nome):
    if not DEBUG_ARTIFACTS_ENABLED:
        return {}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    debug_dir = Path(DOWNLOAD_DIR) / "_debug_selenium"
    debug_dir.mkdir(parents=True, exist_ok=True)
    nome_base = _sanitizar_nome_arquivo(nome or "snapshot")
    png_path = debug_dir / f"{timestamp}_{nome_base}.png"
    html_path = debug_dir / f"{timestamp}_{nome_base}.html"

    try:
        driver.save_screenshot(str(png_path))
    except Exception:
        logger.exception("Falha ao salvar screenshot de debug %s.", png_path)

    try:
        html_path.write_text(driver.page_source, encoding="utf-8")
    except Exception:
        logger.exception("Falha ao salvar HTML de debug %s.", html_path)

    logger.info("Snapshot de debug salvo | png=%s | html=%s", png_path, html_path)
    return {"png": str(png_path), "html": str(html_path)}


def _sanitizar_nome_arquivo(valor):
    valor = str(valor or "").strip()
    valor = re.sub(r'[<>:"/\\|?*]+', " ", valor)
    valor = re.sub(r"\s+", " ", valor).strip()
    return valor or "sem_nome"


def _copiar_download_para_sharepoint(relatorio_config, arquivo_origem, registrar_resultado=True):
    arquivo_origem = Path(arquivo_origem)
    destino_informado = str(relatorio_config.get("sharepoint_link", "") or "").strip()
    if not destino_informado:
        caminho_final = str(arquivo_origem)
        if registrar_resultado:
            relatorio_config.setdefault("_arquivos_finais", []).append(caminho_final)
        return caminho_final

    destino_base = _resolver_destino_sharepoint(relatorio_config.get("sharepoint_link", ""))
    if not destino_base:
        raise DownloadProcessingError(
            "copia",
            "O destino informado nao e uma pasta local sincronizada ou caminho UNC valido.",
        )

    try:
        destino_base.mkdir(parents=True, exist_ok=True)
        destino_arquivo = _montar_caminho_download_unico(
            destino_base,
            arquivo_origem.stem,
            arquivo_origem.suffix,
        )
        shutil.copy2(arquivo_origem, destino_arquivo)
        if not destino_arquivo.exists() or destino_arquivo.stat().st_size != arquivo_origem.stat().st_size:
            raise OSError("A copia no destino nao foi confirmada ou ficou incompleta.")
        logger.info("Download copiado para SharePoint/local | origem=%s | destino=%s", arquivo_origem, destino_arquivo)
        caminho_final = str(destino_arquivo)
        if registrar_resultado:
            relatorio_config.setdefault("_arquivos_finais", []).append(caminho_final)
        return caminho_final
    except OSError as exc:
        logger.exception(
            "Nao foi possivel copiar o arquivo %s para o destino SharePoint/local '%s'.",
            arquivo_origem,
            destino_base,
        )
        raise DownloadProcessingError("copia", f"Falha ao copiar o arquivo para o destino: {exc}") from exc


def _resolver_destino_sharepoint(sharepoint_link):
    destino = str(sharepoint_link or "").strip()
    if not destino:
        return None

    if destino.lower().startswith(("http://", "https://")):
        logger.warning(
            "URL web do SharePoint informada (%s), mas upload direto por URL ainda nao esta implementado. "
            "Use uma pasta local sincronizada/UNC para copia automatica.",
            destino,
        )
        return None

    caminho = Path(destino).expanduser()
    if caminho.name.strip().lower() == "automação cap".lower():
        return caminho

    return caminho / "Automação CAP"


def _copiar_texto_para_area_transferencia(texto):
    if os.name != "nt":
        raise RuntimeError("A simulacao de colagem esta disponivel apenas no Windows.")

    texto = str(texto or "")
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = 13

    if not user32.OpenClipboard(None):
        raise RuntimeError("Nao foi possivel abrir a area de transferencia do Windows.")

    try:
        user32.EmptyClipboard()
        buffer = ctypes.create_unicode_buffer(texto)
        buffer_size = ctypes.sizeof(buffer)
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, buffer_size)
        if not handle:
            raise RuntimeError("Nao foi possivel alocar memoria para a area de transferencia.")

        locked_memory = kernel32.GlobalLock(handle)
        if not locked_memory:
            kernel32.GlobalFree(handle)
            raise RuntimeError("Nao foi possivel bloquear a memoria da area de transferencia.")

        try:
            ctypes.memmove(locked_memory, buffer, buffer_size)
        finally:
            kernel32.GlobalUnlock(handle)

        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            raise RuntimeError("Nao foi possivel gravar o texto na area de transferencia.")
    finally:
        user32.CloseClipboard()


def _pressionar_tabs_consecutivos(driver, quantidade):
    driver.switch_to.default_content()
    for _ in range(max(0, int(quantidade or 0))):
        ActionChains(driver).send_keys(Keys.TAB).perform()
        time.sleep(0.15)


def normalizar_acao(acao):
    return (acao or "").strip().lower()
