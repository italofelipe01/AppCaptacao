"""
Instala a configuracao da aplicacao em uma pasta oculta do Windows.
"""

from __future__ import annotations

import argparse
import getpass
import os
import shutil
from pathlib import Path

from app_config import (
    APP_ENV_FILENAME,
    APP_ENV_ENCRYPTED_FILENAME,
    encrypt_env_file,
    encrypt_text_for_current_user,
    ensure_config_dir,
    get_fallback_config_dir,
    get_hidden_config_dir,
    get_hidden_config_path,
    get_runtime_config_dir,
    is_encrypted_env_path,
    mark_path_hidden,
    mark_path_normal,
)


INTERACTIVE_DEFAULTS = {
    "FLASK_SECRET_KEY": "app-captacao",
    "APP_HOST": "127.0.0.1",
    "APP_PORT": "4732",
    "APP_DEBUG": "false",
    "SIENGE_SESSION_REUSE_ENABLED": "true",
    "SELENIUM_REPORT_WAIT_SECONDS": "8",
    "SELENIUM_DOWNLOAD_WAIT_TIMEOUT_SECONDS": "600",
    "SELENIUM_DOWNLOAD_DIR": "",
    "DB_DRIVER": "SQL Server",
    "DB_HOST": "",
    "DB_DATABASE": "<valor removido>",
    "DB_SCHEMA": "dbo",
    "DB_USER": "",
    "DB_PASSWORD": "",
    "DB_EXTRA_PARAMS": "",
    "DB_TIMEOUT": "5",
    "CAP_OPERACOES_LOGIN_CRIACAO": "1",
    "RELATORIO_X_OPERACAO_TABLE": "dbo.CapRecursoRelatorio_X_Operacao",
    "FILTRO_X_OPERACAO_TABLE": "dbo.CapRecursoFiltro_X_Operacao",
    "FILTRO_CATALOGO_TABLE": "dbo.CapRecursoFiltro",
    "USUARIO_TABLE": "dbo.CapRecursoUsuario",
    "DEV_BOOTSTRAP_ADMIN_ENABLED": "false",
    "DEV_BOOTSTRAP_ADMIN_ID": "999999",
    "DEV_BOOTSTRAP_ADMIN_LOGIN": "admin",
    "DEV_BOOTSTRAP_ADMIN_PASSWORD_HASH": "",
    "DEV_BOOTSTRAP_ADMIN_EMAIL": "admin@local.test",
    "DEV_BOOTSTRAP_ADMIN_AREA": "performance",
    "DEV_BOOTSTRAP_ADMIN_ACCESS_ID": "1",
}

SECRET_FIELDS = {"DB_PASSWORD", "FLASK_SECRET_KEY", "DEV_BOOTSTRAP_ADMIN_PASSWORD_HASH"}


def _copy_config_file(source: Path, target: Path) -> Path:
    temp_target = target.with_suffix(target.suffix + ".tmp")
    if temp_target.exists():
        temp_target.unlink()

    shutil.copyfile(source, temp_target)
    mark_path_normal(target)
    os.replace(temp_target, target)
    mark_path_hidden(target)
    return target


def _install_encrypted_config_file(source: Path, target: Path) -> Path:
    temp_target = target.with_suffix(target.suffix + ".tmp")
    if temp_target.exists():
        temp_target.unlink()

    encrypt_env_file(source, temp_target)
    mark_path_normal(target)
    os.replace(temp_target, target)
    mark_path_hidden(target)
    return target


def _install_encrypted_text(plaintext: str, target: Path) -> Path:
    temp_target = target.with_suffix(target.suffix + ".tmp")
    if temp_target.exists():
        temp_target.unlink()

    temp_target.write_text(encrypt_text_for_current_user(plaintext), encoding="utf-8")
    mark_path_normal(target)
    os.replace(temp_target, target)
    mark_path_hidden(target)
    return target


def _target_dirs(portable: bool) -> list[Path]:
    if portable:
        return [get_runtime_config_dir()]
    return [get_hidden_config_dir(), get_fallback_config_dir()]


def install_config(
    source: Path,
    *,
    encrypt: bool = False,
    portable: bool = False,
    delete_source: bool = False,
) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"Arquivo de origem nao encontrado: {source}")

    last_error: Exception | None = None
    target_filename = APP_ENV_ENCRYPTED_FILENAME if encrypt else APP_ENV_FILENAME

    for config_dir in _target_dirs(portable):
        try:
            target = ensure_config_dir(config_dir) / target_filename
            if encrypt and not is_encrypted_env_path(source):
                installed = _install_encrypted_config_file(source, target)
            else:
                installed = _copy_config_file(source, target)

            if delete_source:
                source.unlink()
            return installed
        except OSError as exc:
            last_error = exc

    raise PermissionError(
        "Nao foi possivel instalar a configuracao em nenhuma pasta do usuario. "
        f"Tentativa principal: {get_hidden_config_path()}. "
        f"Ultimo erro: {last_error}"
    )


def install_config_text(plaintext: str, *, encrypt: bool = False, portable: bool = False) -> Path:
    last_error: Exception | None = None
    target_filename = APP_ENV_ENCRYPTED_FILENAME if encrypt else APP_ENV_FILENAME

    for config_dir in _target_dirs(portable):
        try:
            target = ensure_config_dir(config_dir) / target_filename
            if encrypt:
                return _install_encrypted_text(plaintext, target)

            temp_target = target.with_suffix(target.suffix + ".tmp")
            temp_target.write_text(plaintext, encoding="utf-8")
            mark_path_normal(target)
            os.replace(temp_target, target)
            mark_path_hidden(target)
            return target
        except OSError as exc:
            last_error = exc

    raise PermissionError(
        "Nao foi possivel instalar a configuracao em nenhuma pasta do usuario. "
        f"Tentativa principal: {get_hidden_config_path()}. "
        f"Ultimo erro: {last_error}"
    )


def _prompt_interactive_config() -> str:
    linhas = []
    print("Informe a configuracao desta maquina. Pressione Enter para usar o padrao entre colchetes.")
    for chave, padrao in INTERACTIVE_DEFAULTS.items():
        if chave in SECRET_FIELDS:
            valor = getpass.getpass(f"{chave}{' [' + padrao + ']' if padrao else ''}: ").strip()
        else:
            valor = input(f"{chave}{' [' + padrao + ']' if padrao else ''}: ").strip()
        if not valor:
            valor = padrao
        linhas.append(f"{chave}={valor}")
    return "\n".join(linhas) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Instala o arquivo de configuracao oculto do AppCaptacao."
    )
    parser.add_argument(
        "--source",
        default=".env",
        help="Arquivo de origem com as variaveis de ambiente. Padrao: .env",
    )
    parser.add_argument(
        "--encrypt",
        action="store_true",
        help="Instala criptografado com DPAPI no Windows. Padrao: instalar sem criptografia.",
    )
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Instala na pasta .config ao lado do script/executavel. Padrao: perfil do usuario.",
    )
    parser.add_argument(
        "--delete-source",
        action="store_true",
        help="Apaga o arquivo de origem apos instalar com sucesso.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Pergunta as variaveis no terminal e instala sem criar arquivo .env visivel.",
    )
    args = parser.parse_args()

    if args.interactive:
        plaintext = _prompt_interactive_config()
        target = install_config_text(plaintext, encrypt=args.encrypt, portable=args.portable)
    else:
        target = install_config(
            Path(args.source).resolve(),
            encrypt=args.encrypt,
            portable=args.portable,
            delete_source=args.delete_source,
        )
    print(f"Configuracao instalada em: {target}")


if __name__ == "__main__":
    main()
