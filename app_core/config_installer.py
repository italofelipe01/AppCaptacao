from __future__ import annotations

import secrets
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import customtkinter as ctk
    from tkinter import filedialog, messagebox
except ImportError:  # pragma: no cover
    raise

from app_core.app_config import (
    APP_ENV_ENCRYPTED_FILENAME,
    decrypt_env_file,
    get_existing_config_path,
    get_hidden_config_dir,
    get_hidden_encrypted_config_path,
    get_runtime_base_dir,
    install_encrypted_config_text,
    remove_local_configuration,
)


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


DEFAULT_ENV_TEMPLATE = """# AppCaptacao - configuracao segura por usuario
FLASK_SECRET_KEY=
APP_HOST=127.0.0.1
APP_PORT=4732
APP_DEBUG=false

DB_DRIVER=SQL Server
DB_HOST=
DB_DATABASE=
DB_SCHEMA=dbo
DB_USER=
DB_PASSWORD=
DB_EXTRA_PARAMS=
DB_TIMEOUT=5

SIENGE_LOGIN_URL=https://ebm.sienge.com.br/sienge/
SIENGE_SESSION_REUSE_ENABLED=true
SIENGE_FORCE_INTERACTIVE_LOGIN=false
SELENIUM_BROWSER=edge
SELENIUM_KEEP_BROWSER_OPEN=false
EDGE_USE_PROFILE=true
EDGE_USER_DATA_DIR=
EDGE_PROFILE_DIRECTORY=Default
SELENIUM_LOGIN_ACTION_DELAY_SECONDS=8
SELENIUM_DOWNLOAD_DIR=
"""


def _normalize_env_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""
    return normalized + "\n"


def _upsert_env_key(text: str, key: str, value: str) -> str:
    lines = _normalize_env_text(text).splitlines()
    prefix = f"{key}="
    replaced = False
    output: list[str] = []

    for line in lines:
        if line.startswith(prefix):
            output.append(f"{key}={value}")
            replaced = True
        else:
            output.append(line)

    if not replaced:
        output.append(f"{key}={value}")

    return "\n".join(output).strip() + "\n"


class ConfigInstallerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Configurar AppCaptacao")
        self.geometry("980x760")
        self.minsize(900, 700)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.status_var = ctk.StringVar(value=f"Destino seguro: {get_hidden_encrypted_config_path()}")
        self._build_ui()
        self._load_initial_content()

    def _build_ui(self) -> None:
        container = ctk.CTkFrame(self, corner_radius=24)
        container.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(3, weight=1)

        title = ctk.CTkLabel(
            container,
            text="Configurador seguro do AppCaptacao",
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=24, pady=(24, 6))

        subtitle = ctk.CTkLabel(
            container,
            text=(
                "Use este utilitario para importar ou editar a configuracao da maquina e salvar "
                "apenas a versao criptografada no perfil do usuario."
            ),
            justify="left",
            wraplength=840,
            text_color="#475569",
            font=ctk.CTkFont(size=14),
        )
        subtitle.grid(row=1, column=0, sticky="w", padx=24)

        actions = ctk.CTkFrame(container, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=24, pady=(18, 16))
        for column in range(5):
            actions.grid_columnconfigure(column, weight=1)

        self.import_button = ctk.CTkButton(actions, text="Importar .env", command=self._import_env_file, height=42)
        self.import_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.load_button = ctk.CTkButton(actions, text="Carregar atual", command=self._load_existing_config, height=42)
        self.load_button.grid(row=0, column=1, sticky="ew", padx=8)

        self.secret_button = ctk.CTkButton(
            actions,
            text="Gerar secret key",
            command=self._generate_secret_key,
            height=42,
        )
        self.secret_button.grid(row=0, column=2, sticky="ew", padx=8)

        self.save_button = ctk.CTkButton(
            actions,
            text="Salvar criptografado",
            command=self._save_secure_config,
            height=42,
            fg_color="#0f766e",
            hover_color="#115e59",
        )
        self.save_button.grid(row=0, column=3, sticky="ew", padx=8)

        self.remove_button = ctk.CTkButton(
            actions,
            text="Remover configuracao",
            command=self._remove_local_config,
            height=42,
            fg_color="#7f1d1d",
            hover_color="#991b1b",
        )
        self.remove_button.grid(row=0, column=4, sticky="ew", padx=(8, 0))

        self.editor = ctk.CTkTextbox(
            container,
            corner_radius=18,
            font=("Consolas", 14),
            wrap="none",
        )
        self.editor.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 16))

        footer = ctk.CTkFrame(container, corner_radius=18)
        footer.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 24))
        footer.grid_columnconfigure(0, weight=1)

        status_label = ctk.CTkLabel(
            footer,
            textvariable=self.status_var,
            justify="left",
            wraplength=820,
            anchor="w",
            font=ctk.CTkFont(size=13),
        )
        status_label.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))

        notes_label = ctk.CTkLabel(
            footer,
            text=(
                f"Arquivos que nao devem acompanhar a entrega final: .env, {APP_ENV_ENCRYPTED_FILENAME} ao lado do exe, "
                "pasta .config local e qualquer copia de codigo-fonte."
            ),
            justify="left",
            wraplength=820,
            anchor="w",
            text_color="#475569",
            font=ctk.CTkFont(size=12),
        )
        notes_label.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 16))

    def _load_initial_content(self) -> None:
        if not self._load_existing_config(silent=True):
            self.editor.insert("1.0", DEFAULT_ENV_TEMPLATE)

    def _load_existing_config(self, silent: bool = False) -> bool:
        existing_path = get_existing_config_path()
        if not existing_path or not existing_path.exists():
            if not silent:
                messagebox.showinfo("Configurar AppCaptacao", "Nenhuma configuracao existente foi encontrada.")
            return False

        try:
            if existing_path.suffix.lower() == ".enc":
                content = decrypt_env_file(existing_path)
            else:
                content = existing_path.read_text(encoding="utf-8")
        except Exception as exc:
            if not silent:
                messagebox.showerror("Configurar AppCaptacao", f"Nao foi possivel carregar a configuracao atual: {exc}")
            return False

        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", _normalize_env_text(content))
        self.status_var.set(f"Configuracao carregada de: {existing_path}")
        return True

    def _import_env_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="Selecionar arquivo de configuracao",
            filetypes=[("Arquivos de ambiente", "*.env;*.txt;*.enc"), ("Todos os arquivos", "*.*")],
        )
        if not selected:
            return

        selected_path = Path(selected)
        try:
            if selected_path.suffix.lower() == ".enc":
                content = decrypt_env_file(selected_path)
            else:
                content = selected_path.read_text(encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Configurar AppCaptacao", f"Nao foi possivel importar o arquivo: {exc}")
            return

        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", _normalize_env_text(content))
        self.status_var.set(f"Arquivo importado: {selected_path}")

    def _generate_secret_key(self) -> None:
        updated = _upsert_env_key(self.editor.get("1.0", "end"), "FLASK_SECRET_KEY", secrets.token_urlsafe(32))
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", updated)
        self.status_var.set("FLASK_SECRET_KEY renovada no conteudo atual.")

    def _save_secure_config(self) -> None:
        content = _normalize_env_text(self.editor.get("1.0", "end"))
        if not content:
            messagebox.showwarning("Configurar AppCaptacao", "Informe a configuracao antes de salvar.")
            return

        if "FLASK_SECRET_KEY=" not in content:
            content = _upsert_env_key(content, "FLASK_SECRET_KEY", secrets.token_urlsafe(32))
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", content)

        try:
            target = install_encrypted_config_text(content)
        except Exception as exc:
            messagebox.showerror("Configurar AppCaptacao", f"Nao foi possivel salvar a configuracao: {exc}")
            return

        self.status_var.set(f"Configuracao segura salva em: {target}")
        messagebox.showinfo(
            "Configurar AppCaptacao",
            (
                "Configuracao salva com sucesso.\n\n"
                "Agora voce pode excluir qualquer .env em texto puro usado durante a configuracao."
            ),
        )

    def _remove_local_config(self) -> None:
        confirmed = messagebox.askyesno(
            "Configurar AppCaptacao",
            (
                "Isso remove a configuracao local criptografada e os caches locais do AppCaptacao "
                f"em {get_hidden_config_dir()}.\n\nDeseja continuar?"
            ),
        )
        if not confirmed:
            return

        try:
            removed = remove_local_configuration()
        except Exception as exc:
            messagebox.showerror("Configurar AppCaptacao", f"Nao foi possivel remover a configuracao: {exc}")
            return

        if removed:
            self.status_var.set("Configuracao local removida com sucesso.")
            messagebox.showinfo(
                "Configurar AppCaptacao",
                "Configuracao local removida. Se existir uma copia .env fora do perfil do usuario, exclua-a manualmente.",
            )
        else:
            self.status_var.set("Nenhuma configuracao local foi encontrada para remocao.")
            messagebox.showinfo("Configurar AppCaptacao", "Nenhum arquivo local de configuracao foi encontrado.")


def main() -> None:
    app = ConfigInstallerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
