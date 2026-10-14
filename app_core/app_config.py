"""
Configuracao central da aplicacao AppCaptacao.
"""

from __future__ import annotations

import ctypes
import base64
import io
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

APP_NAME = "AppCaptacao"
APP_ENV_FILENAME = "app_captacao.env"
APP_ENV_ENCRYPTED_FILENAME = "app_captacao.env.enc"
APP_RUNTIME_PLAINTEXT_FLAG = "APP_CAPTACAO_ALLOW_PLAINTEXT_ENV"
APP_STATE_DIRNAME = "state"
FILE_ATTRIBUTE_HIDDEN = 0x02
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF

CRYPTPROTECT_UI_FORBIDDEN = 0x01


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def get_runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_bundle_base_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parent.parent


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
    return Path(__file__).resolve().parent.parent / ".env"


def get_local_dev_encrypted_env_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".env.enc"


def get_state_dir() -> Path:
    return get_hidden_config_dir() / APP_STATE_DIRNAME


def get_sienge_session_store_dir() -> Path:
    return get_state_dir() / "sienge_sessions"


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
    candidates = _encrypted_config_path_candidates()
    if not is_frozen_runtime() or allow_plaintext_config_in_frozen():
        candidates.extend(_plaintext_config_path_candidates())
    return list(dict.fromkeys(candidates))


def initialize_environment() -> Path | None:
    for existing_config_path in get_config_path_candidates():
        if not existing_config_path.exists():
            continue
        try:
            _load_environment_from_path(existing_config_path)
            return existing_config_path
        except Exception:
            continue

    return None


def _load_environment_from_path(path: Path) -> None:
    if path.suffix.lower() == ".enc":
        decrypted_text = decrypt_env_file(path)
        load_dotenv(stream=io.StringIO(decrypted_text), override=False)
        return
    load_dotenv(path, override=False)


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


def encrypt_text_for_current_user(plaintext: str) -> str:
    raw = _protect_bytes_for_current_user(plaintext.encode("utf-8"))
    return base64.b64encode(raw).decode("ascii")


def encrypt_bytes_for_current_user(payload: bytes) -> bytes:
    return _protect_bytes_for_current_user(payload)


def decrypt_text_for_current_user(encoded_payload: str) -> str:
    raw = base64.b64decode(encoded_payload.encode("ascii"))
    decrypted = _unprotect_bytes_for_current_user(raw)
    return decrypted.decode("utf-8")


def decrypt_bytes_for_current_user(payload: bytes) -> bytes:
    return _unprotect_bytes_for_current_user(payload)


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


def _protect_bytes_for_current_user(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Criptografia DPAPI disponivel apenas no Windows.")

    in_blob, in_buffer = _bytes_to_blob(data)
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _unprotect_bytes_for_current_user(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Criptografia DPAPI disponivel apenas no Windows.")

    in_blob, in_buffer = _bytes_to_blob(data)
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _bytes_to_blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array]:
    buffer = (ctypes.c_byte * len(data))(*data) if data else (ctypes.c_byte * 1)()
    blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    return blob, buffer


def get_template_path() -> str:
    return str(get_bundle_base_dir() / "project" / "templates")


def get_static_path() -> str:
    return str(get_bundle_base_dir() / "project" / "static")
