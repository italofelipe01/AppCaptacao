"""Ponto de entrada do AppCaptacao em desenvolvimento (python run.py).

Antes de abrir o app, confere Python, bibliotecas, configuracao, navegador,
pasta de downloads e banco. Opcoes:
  --somente-verificar   roda o checklist e sai, sem abrir o app
  --sem-verificacao     abre direto, sem checklist
"""

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app_captacao import inicializacao  # noqa: E402  (so biblioteca padrao)


def _browser_url() -> str:
    host = (os.getenv("APP_HOST", "127.0.0.1") or "127.0.0.1").strip()
    if host in {"0.0.0.0", "::", ""}:
        host = "127.0.0.1"
    port = int(os.getenv("APP_PORT", "4732"))
    return f"http://{host}:{port}/"


def _app_already_running() -> bool:
    port = int(os.getenv("APP_PORT", "4732"))
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _open_browser(url: str) -> None:
    if os.name == "nt" and hasattr(os, "startfile"):
        os.startfile(url)
    else:
        webbrowser.open(url, new=2)


def _open_browser_when_ready() -> None:
    url = _browser_url()
    port = int(os.getenv("APP_PORT", "4732"))
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                _open_browser(url)
                return
        except OSError:
            time.sleep(0.4)
    print(f"Nao foi possivel abrir automaticamente. Acesse manualmente: {url}")


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inicia o AppCaptacao.")
    parser.add_argument("--somente-verificar", action="store_true", help="roda o checklist e sai")
    parser.add_argument("--sem-verificacao", action="store_true", help="abre o app sem o checklist")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    # Mantem a ordem das mensagens quando o pip escreve no mesmo console.
    reconfigurar = getattr(sys.stdout, "reconfigure", None)
    if reconfigurar:
        reconfigurar(line_buffering=True)
    args = _argumentos(argv)
    verificar = not args.sem_verificacao

    if verificar:
        print("Verificando o ambiente do AppCaptacao...")
        if not (inicializacao.verificar_python() and inicializacao.garantir_dependencias()):
            return 1

    from app_captacao.core.config.environment import initialize_environment

    initialize_environment()
    url = _browser_url()
    if _app_already_running() and not args.somente_verificar:
        print(f"AppCaptacao ja esta em execucao em {url}")
        _open_browser(url)
        return 0

    if verificar and not inicializacao.verificar_configuracao_e_servicos():
        return 1
    if args.somente_verificar:
        return 0

    from app_captacao.app import run_application
    from app_captacao.core.shared.log_tecnico import configurar_log_tecnico

    arquivo_de_log = configurar_log_tecnico()
    print(f"AppCaptacao iniciando em {url}")
    print(f"Log tecnico: {arquivo_de_log}")
    print("Mantenha esta janela aberta enquanto estiver usando o aplicativo.")
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    try:
        run_application(use_waitress=True, open_browser=False)
    except KeyboardInterrupt:
        print("AppCaptacao encerrado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
