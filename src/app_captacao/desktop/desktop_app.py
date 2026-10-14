from __future__ import annotations

import ctypes
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


# Executado como script (PyInstaller ou python <arquivo>): garante src/ no sys.path.
SRC_DIR = Path(__file__).resolve().parents[2]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(
            0,
            "A biblioteca CustomTkinter nao esta instalada. Instale as dependencias do projeto antes de abrir o aplicativo.",
            "AppCaptacao",
            0x10,
        )
    raise

from app_captacao.app import run_application
from app_captacao.core.config.environment import initialize_environment
from app_captacao.core.shared.log_tecnico import configurar_log_tecnico


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


def _server_host() -> str:
    host = os.getenv("APP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    return "127.0.0.1" if host in {"0.0.0.0", "::"} else host


def _server_port() -> int:
    return int(os.getenv("APP_PORT", "4732"))


def _server_url() -> str:
    return f"http://{_server_host()}:{_server_port()}/"


def _is_server_up(timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((_server_host(), _server_port()), timeout=timeout):
            return True
    except OSError:
        return False


class AppCaptacaoDesktop(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.server_thread: threading.Thread | None = None
        self.server_started_by_app = False

        self.title("AppCaptacao")
        self.geometry("760x460")
        self.minsize(700, 420)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_ui()
        self._refresh_status()

    def _build_ui(self) -> None:
        container = ctk.CTkFrame(self, corner_radius=24)
        container.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
        container.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            container,
            text="Central AppCaptação",
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=28, pady=(28, 8))

        subtitle = ctk.CTkLabel(
            container,
            text="Inicialize o servidor Flask local e abra a aplicacao no navegador.",
            font=ctk.CTkFont(size=15),
            text_color="#64748b",
        )
        subtitle.grid(row=1, column=0, sticky="w", padx=28)

        status_frame = ctk.CTkFrame(container, corner_radius=18)
        status_frame.grid(row=2, column=0, sticky="ew", padx=28, pady=(24, 18))
        status_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Verificando servidor...",
            anchor="w",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.status_label.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 6))

        self.url_label = ctk.CTkLabel(
            status_frame,
            text=_server_url(),
            anchor="w",
            font=ctk.CTkFont(size=13),
            text_color="#0f766e",
        )
        self.url_label.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 18))

        info_text = (
            "Se o servidor ja estiver ativo, voce pode abrir a interface direto no navegador. "
            "Se nao estiver, clique em 'Iniciar servidor'."
        )
        self.info_label = ctk.CTkLabel(
            container,
            text=info_text,
            justify="left",
            wraplength=620,
            anchor="w",
            font=ctk.CTkFont(size=14),
        )
        self.info_label.grid(row=3, column=0, sticky="ew", padx=28)

        actions = ctk.CTkFrame(container, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", padx=28, pady=(28, 18))
        actions.grid_columnconfigure((0, 1, 2), weight=1)

        self.start_button = ctk.CTkButton(
            actions,
            text="Iniciar servidor",
            command=self._start_server,
            height=44,
            corner_radius=14,
        )
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.open_button = ctk.CTkButton(
            actions,
            text="Abrir no navegador",
            command=self._open_browser,
            height=44,
            corner_radius=14,
            fg_color="#0f172a",
            hover_color="#1e293b",
        )
        self.open_button.grid(row=0, column=1, sticky="ew", padx=8)

        self.refresh_button = ctk.CTkButton(
            actions,    
            text="Atualizar status",
            command=self._refresh_status,
            height=44,
            corner_radius=14,
            fg_color="#e2e8f0",
            hover_color="#cbd5e1",
            text_color="#0f172a",
        )
        self.refresh_button.grid(row=0, column=2, sticky="ew", padx=(8, 0))

        footer = ctk.CTkLabel(
            container,
            text="Dica: a aplicacao web usa as configuracoes do .env carregadas por app_config.py.",
            font=ctk.CTkFont(size=12),
            text_color="#64748b",
        )
        footer.grid(row=5, column=0, sticky="w", padx=28, pady=(0, 24))

    def _refresh_status(self) -> None:
        server_up = _is_server_up()
        if server_up:
            self.status_label.configure(text="Servidor em execucao.")
            self.info_label.configure(
                text="A interface Flask esta respondendo. Voce pode abrir ou recarregar a aplicacao no navegador."
            )
            self.start_button.configure(state="disabled")
        else:
            self.status_label.configure(text="Servidor parado.")
            self.info_label.configure(
                text="O servidor Flask ainda nao esta em execucao. Clique em 'Iniciar servidor' para subir a aplicacao."
            )
            self.start_button.configure(state="normal")

    def _start_server(self) -> None:
        if _is_server_up():
            self._refresh_status()
            self._open_browser()
            return

        if self.server_thread and self.server_thread.is_alive():
            self.status_label.configure(text="Inicializacao em andamento...")
            return

        self.status_label.configure(text="Inicializando servidor...")
        self.start_button.configure(state="disabled")

        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        self.after(800, self._wait_for_server)

    def _run_server(self) -> None:
        self.server_started_by_app = True
        try:
            # A propria janela abre o navegador quando o servidor responde.
            run_application(use_waitress=True, open_browser=False)
        except Exception as exc:  # pragma: no cover
            self.after(0, lambda: self._handle_server_error(str(exc)))

    def _wait_for_server(self, attempts: int = 0) -> None:
        if _is_server_up():
            self._refresh_status()
            self._open_browser()
            return

        if attempts >= 25:
            self.status_label.configure(text="Nao foi possivel iniciar o servidor.")
            self.start_button.configure(state="normal")
            return

        self.status_label.configure(text="Aguardando servidor responder...")
        self.after(800, lambda: self._wait_for_server(attempts + 1))

    def _handle_server_error(self, message: str) -> None:
        self.status_label.configure(text="Erro ao iniciar o servidor.")
        self.info_label.configure(text=message)
        self.start_button.configure(state="normal")

    def _open_browser(self) -> None:
        webbrowser.open(_server_url(), new=2)


def main() -> None:
    initialize_environment()
    configurar_log_tecnico(console=False)
    app = AppCaptacaoDesktop()
    app.mainloop()


if __name__ == "__main__":
    main()
