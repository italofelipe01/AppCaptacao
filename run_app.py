"""Ponto de entrada da nova versao do AppCaptacao."""

import os
import socket
import threading
import time
import webbrowser

from app_core.app import run_application
from app_core.app_config import initialize_environment


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


if __name__ == "__main__":
    initialize_environment()
    url = _browser_url()
    if _app_already_running():
        print(f"AppCaptacao ja esta em execucao em {url}")
        _open_browser(url)
        raise SystemExit(0)

    print(f"AppCaptacao iniciando em {url}")
    print("Mantenha esta janela aberta enquanto estiver usando o aplicativo.")
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    run_application(use_waitress=True, open_browser=False)
