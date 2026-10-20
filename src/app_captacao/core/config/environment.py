"""Localizacao e carregamento da configuracao (.env) do AppCaptacao.

Em desenvolvimento o .env fica na raiz do repositorio; no executavel a
configuracao fica criptografada (DPAPI) no perfil do usuario. O arquivo vale
sobre variavel de mesmo nome herdada do Windows (D25).
"""

from __future__ import annotations

import ctypes
import io
import os
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values

from app_captacao.core.config.dpapi import (
    decrypt_bytes_for_current_user,
    decrypt_text_for_current_user,
    encrypt_bytes_for_current_user,
    encrypt_text_for_current_user,
)

# src/app_captacao/core/config/environment.py -> raiz do repositorio
PROJECT_ROOT = Path(__file__).resolve().parents[4]

APP_NAME = "AppCaptacao"
APP_ENV_FILENAME = "app_captacao.env"
APP_ENV_ENCRYPTED_FILENAME = "app_captacao.env.enc"
APP_RUNTIME_PLAINTEXT_FLAG = "APP_CAPTACAO_ALLOW_PLAINTEXT_ENV"
APP_STATE_DIRNAME = "state"
FILE_ATTRIBUTE_HIDDEN = 0x02
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF

# Ambiente herdado do Windows antes de qualquer arquivo ser carregado: e com ele que se sabe
# qual variavel de fora (de outro projeto, por exemplo) o arquivo do app deixou de lado.
_AMBIENTE_HERDADO = dict(os.environ)


def get_runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


def get_bundle_base_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return PROJECT_ROOT


def get_windows_appdata_dir() -> Path:
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata).resolve()

    program_data = os.getenv("PROGRAMDATA")
    if program_data:
        return Path(program_data).resolve()

    return Path.home().resolve() / "AppData" / "Local"


def get_hidden_config_dir() -> Path:
    custom_config_dir = os.getenv("APP_CAPTACAO_CONFIG_DIR", "").strip()
    if custom_config_dir:
        return Path(custom_config_dir).expanduser().resolve()
    return get_windows_appdata_dir() / APP_NAME


def get_fallback_config_dir() -> Path:
    return get_windows_appdata_dir() / f"{APP_NAME}Data"


def get_runtime_config_dir() -> Path:
    return get_runtime_base_dir() / ".config"


def get_runtime_env_path() -> Path:
    return get_runtime_base_dir() / ".env"


def get_runtime_config_path() -> Path:
    return get_runtime_config_dir() / APP_ENV_FILENAME


def get_runtime_encrypted_config_path() -> Path:
    return get_runtime_config_dir() / APP_ENV_ENCRYPTED_FILENAME


def get_runtime_portable_config_path() -> Path:
    return get_runtime_base_dir() / APP_ENV_FILENAME


def get_runtime_portable_encrypted_config_path() -> Path:
    return get_runtime_base_dir() / APP_ENV_ENCRYPTED_FILENAME


def is_frozen_runtime() -> bool:
    return bool(getattr(sys, "frozen", False))


def allow_plaintext_config_in_frozen() -> bool:
    return os.getenv(APP_RUNTIME_PLAINTEXT_FLAG, "").strip().lower() in {"1", "true", "yes"}


def get_config_dir_candidates() -> list[Path]:
    custom_config_dir = os.getenv("APP_CAPTACAO_CONFIG_DIR", "").strip()
    if custom_config_dir:
        return [Path(custom_config_dir).expanduser().resolve()]
    return [
        get_hidden_config_dir(),
        get_fallback_config_dir(),
        get_runtime_config_dir(),
    ]


def get_hidden_config_path() -> Path:
    return get_hidden_config_dir() / APP_ENV_FILENAME


def get_hidden_encrypted_config_path() -> Path:
    return get_hidden_config_dir() / APP_ENV_ENCRYPTED_FILENAME


def get_fallback_config_path() -> Path:
    return get_fallback_config_dir() / APP_ENV_FILENAME


def get_fallback_encrypted_config_path() -> Path:
    return get_fallback_config_dir() / APP_ENV_ENCRYPTED_FILENAME


def get_local_dev_env_path() -> Path:
    return PROJECT_ROOT / ".env"


def get_local_dev_encrypted_env_path() -> Path:
    return PROJECT_ROOT / ".env.enc"


def get_state_dir() -> Path:
    return get_hidden_config_dir() / APP_STATE_DIRNAME


def get_temporary_state_dir() -> Path:
    return Path(tempfile.gettempdir()).resolve() / APP_NAME / APP_STATE_DIRNAME


def _ensure_writable_directory(path: Path) -> Path:
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    probe_path = path / f".write_probe_{os.getpid()}"
    try:
        probe_path.write_bytes(b"")
    finally:
        try:
            probe_path.unlink(missing_ok=True)
        except OSError:
            pass
    return path


def get_writable_state_dir() -> Path:
    errors: list[OSError] = []
    for candidate in (get_state_dir(), get_temporary_state_dir()):
        try:
            return _ensure_writable_directory(candidate)
        except OSError as exc:
            errors.append(exc)

    detail = "; ".join(str(error) for error in errors)
    raise PermissionError(
        f"Nao foi possivel criar um diretorio de estado gravavel para {APP_NAME}: {detail}"
    )


def get_sienge_session_store_dir() -> Path:
    return get_writable_state_dir() / "sienge_sessions"


def mark_path_hidden(path: Path) -> None:
    if os.name != "nt" or not path.exists():
        return

    current_attributes = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    if current_attributes == INVALID_FILE_ATTRIBUTES:
        return

    ctypes.windll.kernel32.SetFileAttributesW(
        str(path),
        current_attributes | FILE_ATTRIBUTE_HIDDEN,
    )


def mark_path_normal(path: Path) -> None:
    if os.name != "nt" or not path.exists():
        return

    ctypes.windll.kernel32.SetFileAttributesW(str(path), FILE_ATTRIBUTE_NORMAL)


def ensure_hidden_config_dir() -> Path:
    config_dir = get_hidden_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    mark_path_hidden(config_dir)
    return config_dir


def ensure_config_dir(config_dir: Path) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        mark_path_hidden(config_dir)
    return config_dir


def get_existing_config_path() -> Path | None:
    for candidate in get_config_path_candidates():
        if candidate.exists():
            return candidate
    return None


def _encrypted_config_path_candidates() -> list[Path]:
    candidates = [
        get_hidden_encrypted_config_path(),
        get_fallback_encrypted_config_path(),
        get_runtime_encrypted_config_path(),
        get_runtime_portable_encrypted_config_path(),
        get_runtime_base_dir() / ".env.enc",
    ]

    for config_dir in get_config_dir_candidates():
        candidates.append(config_dir / APP_ENV_ENCRYPTED_FILENAME)
        candidates.append(config_dir / ".env.enc")

    if not is_frozen_runtime():
        candidates.append(get_local_dev_encrypted_env_path())

    return candidates


def _plaintext_config_path_candidates() -> list[Path]:
    candidates = [
        get_runtime_config_path(),
        get_runtime_portable_config_path(),
        get_runtime_env_path(),
        get_hidden_config_path(),
        get_fallback_config_path(),
    ]

    for config_dir in get_config_dir_candidates():
        candidates.append(config_dir / APP_ENV_FILENAME)
        candidates.append(config_dir / ".env")

    if not is_frozen_runtime():
        candidates.append(get_local_dev_env_path())

    return candidates


def get_config_path_candidates() -> list[Path]:
    candidates = []
    if not is_frozen_runtime():
        # Em desenvolvimento, o .env da raiz do repositorio tem prioridade.
        candidates.append(get_local_dev_env_path())
    candidates.extend(_encrypted_config_path_candidates())
    if not is_frozen_runtime() or allow_plaintext_config_in_frozen():
        candidates.extend(_plaintext_config_path_candidates())
    return list(dict.fromkeys(candidates))


_environment_loaded = False
_loaded_config_path: Path | None = None
_variaveis_herdadas_ignoradas: list[str] = []


def initialize_environment(force: bool = False) -> Path | None:
    """Carrega a primeira configuracao encontrada; chamadas seguintes reutilizam o resultado.

    O arquivo vale sobre variavel de mesmo nome herdada do Windows: DB_USER de outro projeto
    no ambiente do usuario nao pode trocar a conta do banco do AppCaptacao (D25). Os nomes
    ignorados ficam em variaveis_herdadas_ignoradas(), para o checklist avisar.
    """
    global _environment_loaded, _loaded_config_path
    if _environment_loaded and not force:
        return _loaded_config_path

    _loaded_config_path = None
    _variaveis_herdadas_ignoradas.clear()
    for existing_config_path in get_config_path_candidates():
        if not existing_config_path.exists():
            continue
        try:
            _load_environment_from_path(existing_config_path)
            _loaded_config_path = existing_config_path
            break
        except Exception:
            continue

    _environment_loaded = True
    return _loaded_config_path


def get_loaded_config_path() -> Path | None:
    return _loaded_config_path


def variaveis_herdadas_ignoradas() -> list[str]:
    """Nomes (nunca valores) das variaveis do Windows que o arquivo de configuracao substituiu."""
    return list(_variaveis_herdadas_ignoradas)


def _load_environment_from_path(path: Path) -> None:
    if path.suffix.lower() == ".enc":
        valores = dotenv_values(stream=io.StringIO(decrypt_env_file(path)))
    else:
        valores = dotenv_values(path)
    _aplicar_configuracao(valores)


def _aplicar_configuracao(valores: dict[str, str | None]) -> None:
    for chave, valor in valores.items():
        if valor is None:
            continue
        herdado = _AMBIENTE_HERDADO.get(chave)
        if not valor.strip() and herdado:
            # Chave vazia no arquivo e "use o padrao", nao "apague o que foi definido".
            continue
        if herdado is not None and herdado != valor and chave not in _variaveis_herdadas_ignoradas:
            _variaveis_herdadas_ignoradas.append(chave)
        os.environ[chave] = valor


def is_encrypted_env_path(path: Path) -> bool:
    return path.suffix.lower() == ".enc"


def encrypt_env_file(source: Path, target: Path | None = None) -> Path:
    source = Path(source).resolve()
    if not source.exists():
        raise FileNotFoundError(f"Arquivo de configuracao nao encontrado: {source}")

    target = Path(target).resolve() if target else _default_encrypted_target(source)
    plaintext = source.read_text(encoding="utf-8")
    encrypted_payload = encrypt_text_for_current_user(plaintext)
    target.write_text(encrypted_payload, encoding="utf-8")
    return target


def decrypt_env_file(source: Path) -> str:
    source = Path(source).resolve()
    payload = source.read_text(encoding="utf-8").strip()
    return decrypt_text_for_current_user(payload)


def _default_encrypted_target(source: Path) -> Path:
    if source.suffix.lower() == ".enc":
        return source
    return source.with_name(f"{source.name}.enc")


def install_encrypted_config_text(plaintext: str, target: Path | None = None) -> Path:
    config_dir = ensure_config_dir(get_hidden_config_dir())
    target_path = Path(target).resolve() if target else config_dir / APP_ENV_ENCRYPTED_FILENAME
    temp_target = target_path.with_suffix(target_path.suffix + ".tmp")
    temp_target.write_text(encrypt_text_for_current_user(plaintext), encoding="utf-8")
    mark_path_normal(target_path)
    os.replace(temp_target, target_path)
    mark_path_hidden(target_path)
    return target_path


def list_cleanup_targets() -> list[Path]:
    targets = [
        get_hidden_encrypted_config_path(),
        get_hidden_config_path(),
        get_fallback_encrypted_config_path(),
        get_fallback_config_path(),
        get_runtime_encrypted_config_path(),
        get_runtime_config_path(),
        get_runtime_portable_encrypted_config_path(),
        get_runtime_portable_config_path(),
        get_runtime_env_path(),
        get_runtime_base_dir() / ".env.enc",
        get_runtime_base_dir() / ".env",
        get_state_dir(),
        get_temporary_state_dir(),
    ]
    if not is_frozen_runtime():
        targets.extend([get_local_dev_encrypted_env_path(), get_local_dev_env_path()])
    return list(dict.fromkeys(targets))


def remove_path_if_exists(path: Path) -> bool:
    if not path.exists():
        return False
    mark_path_normal(path)
    if path.is_dir():
        for child in sorted(path.iterdir(), reverse=True):
            remove_path_if_exists(child)
        path.rmdir()
        return True
    path.unlink()
    return True


def remove_local_configuration() -> list[Path]:
    removed: list[Path] = []
    for target in list_cleanup_targets():
        if remove_path_if_exists(target):
            removed.append(target)
    return removed


def get_template_path() -> str:
    return str(get_bundle_base_dir() / "project" / "templates")


def get_static_path() -> str:
    return str(get_bundle_base_dir() / "project" / "static")
