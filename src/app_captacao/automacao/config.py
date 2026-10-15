"""Configuracao da automacao Selenium no Sienge, lida do ambiente uma unica vez.

Importa o settings primeiro para garantir que o .env ja foi carregado antes de
qualquer os.getenv deste modulo.
"""

from __future__ import annotations

import os
from pathlib import Path

from selenium.webdriver.common.by import By

from app_captacao.core.config import settings  # noqa: F401  (carrega o .env)
from app_captacao.core.config.environment import get_writable_state_dir

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
# Temporario (.crdownload, .tmp...) parado ha mais que isto e download abandonado, nao em andamento.
DOWNLOAD_TEMP_STALE_SECONDS = int(os.getenv("SELENIUM_DOWNLOAD_STALE_TEMP_SECONDS", "300"))

# Tempo de espera após login (segundos)
POST_LOGIN_WAIT = int(os.getenv("SELENIUM_POST_LOGIN_WAIT_SECONDS", "8"))

# Tempo para concluir o desafio MFA/token da Microsoft (segundos)
MICROSOFT_MFA_WAIT = int(os.getenv("SELENIUM_MICROSOFT_MFA_WAIT_SECONDS", "60"))
INTERACTIVE_LOGIN_TIMEOUT = max(
    int(os.getenv("SIENGE_INTERACTIVE_LOGIN_TIMEOUT_SECONDS", "180")),
    MICROSOFT_MFA_WAIT,
)

# Habilitar reutilização de sessão do navegador
SESSION_REUSE_ENABLED = os.getenv("SIENGE_SESSION_REUSE_ENABLED", "true").strip().lower() == "true"

# Navegador Selenium preferencial para a automação
SELENIUM_BROWSER = os.getenv("SELENIUM_BROWSER", "edge").strip().lower()
KEEP_BROWSER_OPEN = os.getenv("SELENIUM_KEEP_BROWSER_OPEN", "false").strip().lower() == "true"
ATTACH_NORMAL_CHROME = os.getenv("SELENIUM_ATTACH_NORMAL_CHROME", "false").strip().lower() == "true"
ATTACH_NORMAL_EDGE = os.getenv("SELENIUM_ATTACH_NORMAL_EDGE", "true").strip().lower() == "true"
CHROME_DEBUG_HOST = os.getenv("SELENIUM_CHROME_DEBUG_HOST", "127.0.0.1").strip() or "127.0.0.1"
CHROME_DEBUG_PORT = int(os.getenv("SELENIUM_CHROME_DEBUG_PORT", "9222"))
CHROME_USER_DATA_DIR = os.getenv("CHROME_USER_DATA_DIR", "").strip()
CHROME_PROFILE_DIRECTORY = os.getenv("CHROME_PROFILE_DIRECTORY", "").strip()
# Perfil persistente e exclusivo da automacao. Nao usa o perfil pessoal do Edge,
# evitando bloqueio do diretorio e mistura de cookies entre navegadores.
EDGE_USE_PROFILE = os.getenv("EDGE_USE_PROFILE", "true").strip().lower() == "true"
EDGE_USER_DATA_DIR = (
    os.getenv("EDGE_USER_DATA_DIR")
    or str(get_writable_state_dir() / "edge_automation_profile")
)
EDGE_PROFILE_DIRECTORY = os.getenv("EDGE_PROFILE_DIRECTORY", "Default").strip() or "Default"
EDGE_DEBUG_HOST = os.getenv("SELENIUM_EDGE_DEBUG_HOST", "127.0.0.1").strip() or "127.0.0.1"
EDGE_DEBUG_PORT = int(os.getenv("SELENIUM_EDGE_DEBUG_PORT", "9223"))

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
