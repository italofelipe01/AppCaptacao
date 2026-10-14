from __future__ import annotations

import ctypes
import os
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path

try:
    import customtkinter as ctk
except ImportError as exc:  # pragma: no cover
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(
            0,
            "A biblioteca CustomTkinter não está instalada. Instale as dependências do projeto antes de abrir o aplicativo.",
            "AppCaptacao",
            0x10,
        )
    raise

try:
    from tkcalendar import DateEntry
except ImportError:  # pragma: no cover
    DateEntry = None

from app_config import get_bundle_base_dir, get_runtime_env_path, initialize_environment
from desktop_backend import DesktopAppError, DesktopBackend, DesktopPermissionError


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

APP_BG = "#F3F7FB"
PANEL_BG = "#FFFFFF"
SUBPANEL_BG = "#EAF1F8"
SIDEBAR_BG = "#DCE8F3"
SIDEBAR_HOVER = "#C8DAEC"
TEXT_MUTED = "#5B6B7D"
TEXT_STRONG = "#102033"
ACCENT = "#0891B2"
ACCENT_HOVER = "#0E7490"
ACCENT_TEXT = "#ECFEFF"
SUCCESS_TEXT = "#0F766E"
ERROR_TEXT = "#B91C1C"
DANGER_BG = "#B91C1C"
DANGER_HOVER = "#991B1B"
NEW_BG = "#16A34A"
NEW_HOVER = "#15803D"
EDIT_BG = "#94A3B8"
EDIT_HOVER = "#7C8EA3"


ACCESS_LABELS = {
    1: "Administrador",
    2: "Cadastro de operacao",
    3: "Execucao",
}

ACCESS_OPTIONS = [
    ("Administrador", 1),
    ("Cadastro de operacao", 2),
    ("Execucao", 3),
]


def build_unique_label_map(items: list[dict], name_key: str = "nome", id_key: str = "id") -> dict[str, dict]:
    counts: dict[str, int] = {}
    for item in items:
        base = str(item.get(name_key, "")).strip() or f"Item {item.get(id_key, '')}"
        counts[base] = counts.get(base, 0) + 1

    label_map: dict[str, dict] = {}
    used_labels: set[str] = set()
    for item in items:
        base = str(item.get(name_key, "")).strip() or f"Item {item.get(id_key, '')}"
        label = base if counts[base] == 1 else f"{base} [ID {item.get(id_key)}]"
        if label in used_labels:
            suffix = 2
            unique_label = f"{label} ({suffix})"
            while unique_label in used_labels:
                suffix += 1
                unique_label = f"{label} ({suffix})"
            label = unique_label
        used_labels.add(label)
        label_map[label] = item

    return label_map


class LoginFrame(ctk.CTkFrame):
    def __init__(self, master: "DesktopApplication") -> None:
        super().__init__(master, fg_color=APP_BG)
        self.master = master

        card = ctk.CTkFrame(self, width=460, corner_radius=28, fg_color=PANEL_BG, border_width=1, border_color="#D7E2EE")
        card.place(relx=0.5, rely=0.5, anchor="center")

        logo = master.load_logo((130, 80))
        if logo is not None:
            ctk.CTkLabel(card, image=logo, text="").pack(padx=36, pady=(30, 10))

        ctk.CTkLabel(card, text="Central de Extração EBM", font=ctk.CTkFont(size=28, weight="bold")).pack(
            padx=36, pady=(6, 12)
        )
        ctk.CTkLabel(
            card,
            text="Entre com seu usuario para acessar a automacao desktop.",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=14),
        ).pack(padx=36, pady=(0, 24))

        self.login_entry = ctk.CTkEntry(card, placeholder_text="Usuario", width=360, height=42)
        self.login_entry.pack(padx=36, pady=10)

        self.password_entry = ctk.CTkEntry(card, placeholder_text="Senha", show="*", width=360, height=42)
        self.password_entry.pack(padx=36, pady=10)
        self.password_entry.bind("<Return>", lambda _event: self._submit())

        self.message_label = ctk.CTkLabel(card, text="", text_color=ERROR_TEXT, wraplength=360)
        self.message_label.pack(padx=36, pady=(6, 0))

        ctk.CTkButton(
            card,
            text="Entrar",
            width=360,
            height=46,
            corner_radius=14,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT,
            command=self._submit,
        ).pack(padx=36, pady=(24, 36))

    def _submit(self) -> None:
        try:
            user = self.master.backend.login(self.login_entry.get(), self.password_entry.get())
        except DesktopAppError as exc:
            self.message_label.configure(text=str(exc))
            return
        self.message_label.configure(text="")
        self.master.show_shell(user)


class SidebarButton(ctk.CTkButton):
    def __init__(self, master: ctk.CTkBaseClass, text: str, command) -> None:
        super().__init__(
            master,
            text=text,
            command=command,
            corner_radius=14,
            height=42,
            fg_color="transparent",
            hover_color=SIDEBAR_HOVER,
            text_color=TEXT_STRONG,
            anchor="w",
        )


class SearchableComboBox(ctk.CTkFrame):
    def __init__(self, master, values: list[str], command=None, width: int | None = None) -> None:
        super().__init__(master, fg_color="transparent")
        self.command = command
        self.all_values = list(values)
        self.var = tk.StringVar()
        self.option_menu = ctk.CTkOptionMenu(
            self,
            variable=self.var,
            values=self.all_values or [""],
            command=self._handle_change,
            height=34,
            corner_radius=12,
            fg_color=PANEL_BG,
            button_color="#E2E8F0",
            button_hover_color="#CBD5E1",
            text_color=TEXT_STRONG,
            dropdown_fg_color=PANEL_BG,
            dropdown_text_color=TEXT_STRONG,
            dropdown_hover_color=SUBPANEL_BG,
            anchor="w",
            dynamic_resizing=False,
        )
        if width:
            self.option_menu.configure(width=width)
        self.option_menu.pack(fill="x", expand=True)

    def _handle_change(self, _value=None) -> None:
        if callable(self.command):
            self.command(self.get())

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, value: str) -> None:
        self.var.set(value)
        self.option_menu.set(value)

    def set_values(self, values: list[str]) -> None:
        self.all_values = list(values)
        self.option_menu.configure(values=self.all_values or [""])
        if self.get() not in self.all_values and self.all_values:
            self.option_menu.set(self.all_values[0])

    def set_state(self, state: str) -> None:
        disabled = state == "disabled"
        self.option_menu.configure(
            state="disabled" if disabled else "normal",
            fg_color="#F1F5F9" if disabled else PANEL_BG,
            button_color="#E2E8F0" if disabled else "#E2E8F0",
            button_hover_color="#E2E8F0" if disabled else "#CBD5E1",
            text_color=TEXT_MUTED if disabled else TEXT_STRONG,
        )


class AutomationView(ctk.CTkFrame):
    def __init__(self, master: "ShellFrame", backend: DesktopBackend) -> None:
        super().__init__(master.content_frame, fg_color="transparent")
        self.master_shell = master
        self.backend = backend
        self.report_map: dict[str, dict] = {}
        self.operation_map: dict[str, dict] = {}
        self.filter_inputs: dict[str, dict] = {}
        self.current_report_config: dict | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, corner_radius=24, fg_color=PANEL_BG)
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(2, 4))
        header.grid_columnconfigure(1, weight=1)

        logo = self.master_shell.master.load_logo((118, 80))
        if logo is not None:
            ctk.CTkLabel(header, image=logo, text="").grid(row=0, column=0, rowspan=2, padx=(14, 8), pady=8)

        ctk.CTkLabel(header, text="Bem vindo", font=ctk.CTkFont(size=28, weight="bold")).grid(
            row=0, column=1, sticky="w", padx=(0, 18), pady=(6, 0)
        )
        ctk.CTkLabel(
            header,
            text="Configure credenciais, selecione operacao ou relatorio e execute sem abrir servidor.",
            text_color=TEXT_MUTED,
        ).grid(row=1, column=1, sticky="w", padx=(0, 18), pady=(0, 6))

        self.status_label = ctk.CTkLabel(self, text="", text_color=SUCCESS_TEXT, wraplength=900, justify="left")
        self.status_label.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 2))

        form = ctk.CTkFrame(self, corner_radius=22, fg_color=PANEL_BG)
        form.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 12))
        form.grid_columnconfigure((0, 1), weight=1)
        form.grid_rowconfigure(9, weight=1)

        self.email_entry = self._create_labeled_entry(form, 0, 0, "Email")
        self.password_entry = self._create_labeled_entry(form, 0, 1, "Senha", show="*")
        self.sharepoint_entry = self._create_labeled_entry(form, 1, 0, "Link/Caminho SharePoint", columnspan=2)

        ctk.CTkLabel(form, text="Tipo de execucao", anchor="w").grid(row=4, column=0, sticky="ew", padx=18, pady=(4, 2))
        self.mode_menu = SearchableComboBox(form, ["Relatorio", "Operacao"], command=lambda _value: self._toggle_mode())
        self.mode_menu.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 4))

        ctk.CTkLabel(form, text="Relatorio", anchor="w").grid(row=4, column=1, sticky="ew", padx=18, pady=(4, 2))
        self.report_menu = SearchableComboBox(form, ["Selecione"], command=self._on_report_selected)
        self.report_menu.grid(row=5, column=1, sticky="ew", padx=18, pady=(0, 4))

        ctk.CTkLabel(form, text="Operacao", anchor="w").grid(row=6, column=0, sticky="ew", padx=18, pady=(0, 2))
        self.operation_menu = SearchableComboBox(form, ["Selecione"], command=self._on_operation_selected)
        self.operation_menu.grid(row=7, column=0, sticky="ew", padx=18, pady=(0, 4))

        ctk.CTkLabel(form, text="URL do relatorio", anchor="w").grid(row=6, column=1, sticky="ew", padx=18, pady=(0, 2))
        self.report_url_entry = ctk.CTkEntry(form, height=34)
        self.report_url_entry.grid(row=7, column=1, sticky="ew", padx=18, pady=(0, 4))

        self.filters_status_label = ctk.CTkLabel(form, text="", justify="left", text_color=TEXT_MUTED, wraplength=880)
        self.filters_status_label.grid(row=8, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 2))

        self.filters_frame = ctk.CTkScrollableFrame(form, height=300, corner_radius=18, fg_color=SUBPANEL_BG)
        self.filters_frame.grid(row=9, column=0, columnspan=2, sticky="nsew", padx=18, pady=(0, 8))
        self.filters_frame.grid_columnconfigure(0, weight=1)
        self.filters_frame.grid_columnconfigure(1, weight=1)

        self.execute_button = ctk.CTkButton(
            form,
            text="Executar automacao",
            height=40,
            corner_radius=14,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT,
            command=self.execute,
        )
        self.execute_button.grid(row=10, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 8))

        self.mode_menu.set("Relatorio")
        self._toggle_mode()

    def _create_labeled_entry(
        self,
        parent: ctk.CTkFrame,
        row: int,
        column: int,
        label: str,
        *,
        columnspan: int = 1,
        show: str | None = None,
    ) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, anchor="w").grid(
            row=row * 2, column=column, columnspan=columnspan, sticky="ew", padx=18, pady=(4 if row == 0 else 2, 2)
        )
        entry = ctk.CTkEntry(parent, height=34, show=show)
        entry.grid(row=row * 2 + 1, column=column, columnspan=columnspan, sticky="ew", padx=18, pady=(0, 2))
        return entry

    def load_data(self) -> None:
        try:
            payload = self.backend.get_dashboard_data()
        except DesktopAppError as exc:
            self.status_label.configure(text=str(exc), text_color=ERROR_TEXT)
            return

        self.report_map = build_unique_label_map(payload["relatorios_disponiveis"])
        self.operation_map = build_unique_label_map(payload["operacoes_disponiveis"])

        report_values = list(self.report_map.keys()) or ["Sem relatorios"]
        operation_values = list(self.operation_map.keys()) or ["Sem operacoes"]
        self.report_menu.set_values(report_values)
        self.operation_menu.set_values(operation_values)
        self.report_menu.set(report_values[0])
        self.operation_menu.set(operation_values[0])

        creds = payload["credenciais_execucao"]
        self.email_entry.delete(0, "end")
        self.email_entry.insert(0, creds.get("email", ""))
        self.password_entry.delete(0, "end")
        self.password_entry.insert(0, creds.get("senha", ""))
        self.sharepoint_entry.delete(0, "end")
        self.sharepoint_entry.insert(0, creds.get("sharepoint_link", ""))

        self._toggle_mode()
        self._on_report_selected(self.report_menu.get())

    def _toggle_mode(self) -> None:
        mode = self.mode_menu.get()
        report_enabled = mode == "Relatorio"
        self.report_menu.set_state("normal" if report_enabled else "disabled")
        self.operation_menu.set_state("disabled" if report_enabled else "normal")
        if report_enabled:
            self.report_url_entry.configure(state="normal")
        else:
            self.report_url_entry.configure(state="normal")
            self.report_url_entry.delete(0, "end")
            self.report_url_entry.insert(0, "Selecione uma operacao para ver os relatorios vinculados abaixo.")
            self.report_url_entry.configure(state="disabled")
        if report_enabled:
            self._on_report_selected(self.report_menu.get())
        else:
            self._on_operation_selected(self.operation_menu.get())

    def _clear_filters(self) -> None:
        for child in self.filters_frame.winfo_children():
            child.destroy()
        self.filter_inputs = {}
        self.current_report_config = None
        self.filters_status_label.configure(text="")

    def _add_filters_bottom_spacer(self, item_count: int) -> None:
        spacer_row = (item_count + 1) // 2
        spacer = ctk.CTkFrame(self.filters_frame, fg_color="transparent", height=220)
        spacer.grid(row=spacer_row, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        spacer.grid_propagate(False)

    def _format_filter_detail(self, filtro: dict) -> str:
        details = []
        if filtro.get("tipo_campo"):
            details.append(f"Tipo {filtro['tipo_campo']}")
        if filtro.get("tipo_campo_valor"):
            details.append(f"Valor {filtro['tipo_campo_valor']}")
        details.append(f"Iframe {filtro.get('iframe_index', 0)}")
        if filtro.get("acao"):
            details.append(f"Acao {filtro['acao']}")
        return " | ".join(details)

    def _create_date_input(self, parent, value: str):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        if DateEntry is None:
            fallback = ctk.CTkEntry(container, height=34, placeholder_text="AAAA-MM-DD")
            if value:
                fallback.insert(0, value)
            fallback.pack(fill="x", expand=True)
            return container, {"kind": "entry", "widget": fallback}

        date_entry = DateEntry(
            container,
            date_pattern="yyyy-mm-dd",
            background="#0891B2",
            foreground="white",
            borderwidth=0,
        )
        if value:
            try:
                date_entry.set_date(value)
            except Exception:
                pass
        date_entry.pack(fill="x", expand=True)
        return container, {"kind": "date", "widget": date_entry}

    def _build_filter_widget(self, parent, filtro: dict, value: str):
        tipo = (filtro.get("tipo_campo_valor") or "").strip().upper()

        if tipo == "CLICK":
            box = ctk.CTkFrame(parent, corner_radius=12, fg_color=PANEL_BG)
            ctk.CTkLabel(
                box,
                text="Acao automatica de clique. Nenhum valor precisa ser informado.",
                justify="left",
                text_color=TEXT_MUTED,
                wraplength=420,
            ).pack(fill="x", padx=12, pady=10)
            return box, {"kind": "static", "value": ""}

        if tipo == "DATE":
            return self._create_date_input(parent, value)

        placeholder = filtro.get("campo_identificador") or "Informe o valor"
        if tipo == "STRINGINT":
            placeholder = "numero,numero,numero"
        entry = ctk.CTkEntry(parent, height=34, placeholder_text=placeholder)
        if value:
            entry.insert(0, value)
        return entry, {"kind": "entry", "widget": entry}

    def _get_filter_value(self, key: str) -> str:
        meta = self.filter_inputs.get(key)
        if not meta:
            return ""
        if meta["kind"] == "entry":
            return meta["widget"].get().strip()
        if meta["kind"] == "date":
            return meta["widget"].get().strip()
        return str(meta.get("value", "")).strip()

    def _on_report_selected(self, selection: str) -> None:
        if self.mode_menu.get() != "Relatorio":
            return
        self._clear_filters()
        relatorio = self.report_map.get(selection)
        if not relatorio:
            return
        self.report_url_entry.configure(state="normal")
        self.report_url_entry.delete(0, "end")
        self.report_url_entry.insert(0, relatorio.get("url", ""))
        self.report_url_entry.configure(state="disabled")
        try:
            config = self.backend.get_relatorio_config(int(relatorio["id"]))
        except DesktopAppError as exc:
            self.status_label.configure(text=str(exc), text_color=ERROR_TEXT)
            return

        self.current_report_config = config
        if not config.get("filtros"):
            self.filters_status_label.configure(text="Este relatorio nao possui filtros ativos cadastrados.")
            ctk.CTkLabel(self.filters_frame, text="Este relatorio nao possui filtros dinamicos.", text_color=TEXT_MUTED).grid(
                row=0, column=0, sticky="w", padx=8, pady=8
            )
            return

        self.filters_status_label.configure(text=f"{len(config['filtros'])} filtro(s) carregado(s) a partir do cadastro do relatorio.")
        for index, filtro in enumerate(config["filtros"]):
            card = ctk.CTkFrame(self.filters_frame, corner_radius=14, fg_color=PANEL_BG)
            row = index // 2
            column = index % 2
            card.grid(row=row, column=column, sticky="nsew", padx=8, pady=8)
            card.grid_columnconfigure(0, weight=1)

            label = filtro["nome"] + (" (opcional)" if filtro.get("opcional") else "")
            ctk.CTkLabel(card, text=label, anchor="w", font=ctk.CTkFont(size=14, weight="bold")).grid(
                row=0, column=0, sticky="ew", padx=12, pady=(10, 4)
            )
            widget, meta = self._build_filter_widget(card, filtro, str(filtro.get("valor") or ""))
            widget.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
            self.filter_inputs[f"filtro_{filtro['id']}"] = meta
        self._add_filters_bottom_spacer(len(config["filtros"]))

    def _on_operation_selected(self, selection: str) -> None:
        if self.mode_menu.get() != "Operacao":
            return
        self._clear_filters()
        operacao = self.operation_map.get(selection)
        if not operacao:
            return
        try:
            relatorios = self.backend.get_operacao_config(int(operacao["id"]))
        except DesktopAppError as exc:
            self.status_label.configure(text=str(exc), text_color=ERROR_TEXT)
            return

        if not relatorios:
            self.filters_status_label.configure(text="A operacao selecionada nao possui relatorios ativos.")
            ctk.CTkLabel(self.filters_frame, text="A operacao nao possui relatorios ativos.", text_color=TEXT_MUTED).grid(
                row=0, column=0, sticky="w", padx=8, pady=8
            )
            return

        self.filters_status_label.configure(text=f"{len(relatorios)} relatorio(s) vinculados a esta operacao.")
        for index, relatorio in enumerate(relatorios):
            filtros = relatorio.get("filtros", [])
            resumo = ", ".join(
                f"{filtro['nome']}={filtro.get('valor') or '-'}"
                for filtro in filtros
            ) or "Sem filtros"
            card = ctk.CTkFrame(self.filters_frame, corner_radius=14, fg_color=PANEL_BG)
            row = index // 2
            column = index % 2
            card.grid(row=row, column=column, sticky="nsew", padx=8, pady=8)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(card, text=relatorio["nome"], justify="left", anchor="w", font=ctk.CTkFont(size=14, weight="bold")).grid(
                row=0, column=0, sticky="ew", padx=12, pady=(10, 6)
            )
            ctk.CTkLabel(card, text=relatorio.get("url", ""), justify="left", anchor="w", text_color=SUCCESS_TEXT, wraplength=380).grid(
                row=1, column=0, sticky="ew", padx=12, pady=(0, 6)
            )
            ctk.CTkLabel(card, text=resumo, justify="left", anchor="w", text_color=TEXT_MUTED, wraplength=380).grid(
                row=2, column=0, sticky="ew", padx=12, pady=(0, 12)
            )
        self._add_filters_bottom_spacer(len(relatorios))

    def execute(self) -> None:
        payload = {
            "email": self.email_entry.get().strip(),
            "senha": self.password_entry.get(),
            "sharepoint_link": self.sharepoint_entry.get().strip(),
        }

        try:
            if self.mode_menu.get() == "Relatorio":
                relatorio = self.report_map.get(self.report_menu.get())
                if not relatorio:
                    raise DesktopAppError("Selecione um relatorio para continuar.")
                payload["relatorio_id"] = relatorio["id"]
                for key in self.filter_inputs:
                    payload[key] = self._get_filter_value(key)
                message = self.backend.execute_relatorio(payload)
            else:
                operacao = self.operation_map.get(self.operation_menu.get())
                if not operacao:
                    raise DesktopAppError("Selecione uma operacao para continuar.")
                payload["operacao_id"] = operacao["id"]
                message = self.backend.execute_operacao(payload)
        except DesktopAppError as exc:
            self.status_label.configure(text=str(exc), text_color=ERROR_TEXT)
            return

        self.status_label.configure(text=message, text_color=SUCCESS_TEXT)


class ProfileView(ctk.CTkFrame):
    def __init__(self, master: "ShellFrame", backend: DesktopBackend) -> None:
        super().__init__(master.content_frame, fg_color="transparent")
        self.backend = backend

        ctk.CTkLabel(self, text="Perfil", font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w", padx=24, pady=(24, 8))
        self.info_label = ctk.CTkLabel(self, text="", justify="left", text_color=TEXT_STRONG)
        self.info_label.pack(anchor="w", padx=24, pady=(0, 18))

        box = ctk.CTkFrame(self, corner_radius=22, fg_color=PANEL_BG)
        box.pack(fill="x", padx=24, pady=(0, 24))

        self.current_password = self._entry(box, "Senha atual")
        self.new_password = self._entry(box, "Nova senha")
        self.confirm_password = self._entry(box, "Confirmar nova senha")
        self.message_label = ctk.CTkLabel(box, text="", text_color=SUCCESS_TEXT, wraplength=680)
        self.message_label.pack(anchor="w", padx=18, pady=(6, 0))
        ctk.CTkButton(
            box,
            text="Atualizar senha",
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT,
            command=self.change_password,
        ).pack(anchor="e", padx=18, pady=18)

    def _entry(self, parent: ctk.CTkFrame, label: str) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, anchor="w").pack(fill="x", padx=18, pady=(18, 6))
        entry = ctk.CTkEntry(parent, height=40, show="*")
        entry.pack(fill="x", padx=18, pady=(0, 4))
        return entry

    def load_data(self) -> None:
        user = self.backend.get_profile()
        text = (
            f"Usuario: {user['login']}\n"
            f"Email: {user['email']}\n"
            f"Area: {user['area']}\n"
            f"Perfil: {ACCESS_LABELS.get(user['access_id'], 'Desconhecido')}"
        )
        self.info_label.configure(text=text)
        self.message_label.configure(text="")

    def change_password(self) -> None:
        try:
            message = self.backend.change_password(
                self.current_password.get(),
                self.new_password.get(),
                self.confirm_password.get(),
            )
        except DesktopAppError as exc:
            self.message_label.configure(text=str(exc), text_color=ERROR_TEXT)
            return

        for entry in (self.current_password, self.new_password, self.confirm_password):
            entry.delete(0, "end")
        self.message_label.configure(text=message, text_color=SUCCESS_TEXT)


class GridView(ctk.CTkFrame):
    def __init__(self, master: "ShellFrame", title: str) -> None:
        super().__init__(master.content_frame, fg_color="transparent")
        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w", padx=24, pady=(24, 8))
        self.message_label = ctk.CTkLabel(self, text="", text_color=TEXT_MUTED)
        self.message_label.pack(anchor="w", padx=24, pady=(0, 12))
        self.toolbar = ctk.CTkFrame(self, fg_color="transparent")
        self.toolbar.pack(fill="x", padx=24, pady=(0, 10))
        self.table_frame = ctk.CTkFrame(self, corner_radius=20, fg_color=PANEL_BG)
        self.table_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        self.tree = ttk.Treeview(self.table_frame, show="headings")
        self.tree.pack(fill="both", expand=True, padx=14, pady=14)


class EntityDialog(ctk.CTkToplevel):
    def __init__(self, master, title: str, width: int = 520, height: int = 420) -> None:
        super().__init__(master)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.configure(fg_color=PANEL_BG)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=20, pady=20)

        self.message_label = ctk.CTkLabel(self.body, text="", text_color=ERROR_TEXT, wraplength=440, justify="left")
        self.message_label.pack(fill="x", pady=(0, 8))

    def set_error(self, message: str) -> None:
        self.message_label.configure(text=message)


class UserDialog(EntityDialog):
    def __init__(self, master, backend: DesktopBackend, on_success, user: dict | None = None) -> None:
        super().__init__(master, "Usuario", width=560, height=540)
        self.backend = backend
        self.on_success = on_success
        self.user = user

        form = ctk.CTkFrame(self.body, corner_radius=16, fg_color=PANEL_BG)
        form.pack(fill="both", expand=True)
        form.grid_columnconfigure((0, 1), weight=1)

        self.login_entry = self._entry(form, 0, 0, "Login")
        self.email_entry = self._entry(form, 0, 1, "Email")
        self.area_entry = self._entry(form, 1, 0, "Area", columnspan=2)
        self.access_menu = self._option(form, 2, 0, "Nivel de acesso", [label for label, _ in ACCESS_OPTIONS], columnspan=2)
        self.password_entry = self._entry(form, 3, 0, "Senha", show="*")
        self.confirm_entry = self._entry(form, 3, 1, "Confirmar senha", show="*")

        buttons = ctk.CTkFrame(self.body, fg_color="transparent")
        buttons.pack(fill="x", pady=(12, 0))
        ctk.CTkButton(buttons, text="Cancelar", fg_color="#94A3B8", hover_color="#7C8EA3", command=self.destroy).pack(side="right")
        ctk.CTkButton(buttons, text="Salvar", fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ACCENT_TEXT, command=self.submit).pack(side="right", padx=(0, 10))

        if user:
            self.login_entry.insert(0, user["login"])
            self.login_entry.configure(state="disabled")
            self.email_entry.insert(0, user["email"])
            self.area_entry.insert(0, user["area"])
            self.access_menu.set(user["perfil"])

    def _entry(self, parent, row: int, column: int, label: str, *, columnspan: int = 1, show: str | None = None):
        ctk.CTkLabel(parent, text=label, anchor="w").grid(row=row * 2, column=column, columnspan=columnspan, sticky="ew", padx=12, pady=(10, 4))
        entry = ctk.CTkEntry(parent, height=34, show=show)
        entry.grid(row=row * 2 + 1, column=column, columnspan=columnspan, sticky="ew", padx=12, pady=(0, 4))
        return entry

    def _option(self, parent, row: int, column: int, label: str, values: list[str], *, columnspan: int = 1):
        ctk.CTkLabel(parent, text=label, anchor="w").grid(row=row * 2, column=column, columnspan=columnspan, sticky="ew", padx=12, pady=(10, 4))
        menu = SearchableComboBox(parent, values)
        menu.grid(row=row * 2 + 1, column=column, columnspan=columnspan, sticky="ew", padx=12, pady=(0, 4))
        menu.set(values[0])
        return menu

    def submit(self) -> None:
        selected_access = next((value for label, value in ACCESS_OPTIONS if label == self.access_menu.get()), None)
        payload = {
            "login": self.login_entry.get().strip(),
            "email": self.email_entry.get().strip(),
            "area": self.area_entry.get().strip(),
            "id_acesso": str(selected_access or ""),
            "senha": self.password_entry.get(),
            "confirmar_senha": self.confirm_entry.get(),
            "nova_senha": self.password_entry.get(),
        }

        try:
            if self.user:
                self.backend.update_user(int(self.user["id"]), payload)
            else:
                self.backend.create_user(payload)
        except DesktopAppError as exc:
            self.set_error(str(exc))
            return

        self.on_success()
        self.destroy()


class OperationDialog(EntityDialog):
    def __init__(self, master, backend: DesktopBackend, on_success, operation: dict | None = None) -> None:
        super().__init__(master, "Operacao", width=500, height=240)
        self.backend = backend
        self.on_success = on_success
        self.operation = operation

        ctk.CTkLabel(self.body, text="Nome da operacao", anchor="w").pack(fill="x", pady=(8, 4))
        self.name_entry = ctk.CTkEntry(self.body, height=36)
        self.name_entry.pack(fill="x")

        buttons = ctk.CTkFrame(self.body, fg_color="transparent")
        buttons.pack(fill="x", pady=(20, 0))
        ctk.CTkButton(buttons, text="Cancelar", fg_color="#94A3B8", hover_color="#7C8EA3", command=self.destroy).pack(side="right")
        ctk.CTkButton(buttons, text="Salvar", fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ACCENT_TEXT, command=self.submit).pack(side="right", padx=(0, 10))

        if operation:
            self.name_entry.insert(0, operation["nome"])

    def submit(self) -> None:
        try:
            if self.operation:
                self.backend.update_operation(int(self.operation["id"]), self.name_entry.get().strip())
            else:
                self.backend.create_operation(self.name_entry.get().strip())
        except DesktopAppError as exc:
            self.set_error(str(exc))
            return

        self.on_success()
        self.destroy()


class OperationReportsDialog(EntityDialog):
    def __init__(self, master, backend: DesktopBackend, operation: dict) -> None:
        super().__init__(master, f"Relatorios da Operacao {operation['nome']}", width=980, height=720)
        self.backend = backend
        self.operation = operation
        self.filter_inputs: dict[tuple[int, int], dict] = {}
        self.available_reports_map: dict[str, dict] = {}

        hero = ctk.CTkFrame(self.body, fg_color=SUBPANEL_BG, corner_radius=18)
        hero.pack(fill="x", pady=(0, 12))
        hero.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hero, text="Relatorios da operacao", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 2)
        )
        ctk.CTkLabel(
            hero,
            text=f"Operacao selecionada: {operation['nome']}",
            text_color=TEXT_MUTED,
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))

        controls = ctk.CTkFrame(self.body, fg_color=PANEL_BG, corner_radius=16)
        controls.pack(fill="x", pady=(0, 10))
        controls.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            controls,
            text="Vincular novo relatorio",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            controls,
            text="Escolha um relatorio disponivel e vincule seus filtros automaticos a esta operacao.",
            text_color=TEXT_MUTED,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 10))

        self.report_menu = SearchableComboBox(controls, ["Carregando..."], width=42)
        self.report_menu.grid(row=2, column=0, sticky="ew", padx=(16, 10), pady=(0, 14))
        ctk.CTkButton(
            controls,
            text="🔗 Vincular relatorio",
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=ACCENT_TEXT,
            command=self.add_report,
        ).grid(row=2, column=1, sticky="e", padx=(0, 16), pady=(0, 14))

        self.summary_label = ctk.CTkLabel(self.body, text="", text_color=TEXT_MUTED, justify="left")
        self.summary_label.pack(fill="x", pady=(0, 10))

        self.reports_frame = ctk.CTkScrollableFrame(self.body, fg_color=SUBPANEL_BG, corner_radius=18)
        self.reports_frame.pack(fill="both", expand=True)
        self.reports_frame.grid_columnconfigure(0, weight=1)

        self.load_data()

    def _build_value_widget(self, parent, value: str, tipo: str):
        tipo = (tipo or "").strip().upper()
        if tipo == "DATE":
            container = ctk.CTkFrame(parent, fg_color="transparent")
            if DateEntry is None:
                entry = ctk.CTkEntry(container, height=32, placeholder_text="AAAA-MM-DD")
                if value:
                    entry.insert(0, value)
                entry.pack(fill="x", expand=True)
                return container, {"kind": "entry", "widget": entry}

            date_entry = DateEntry(container, date_pattern="yyyy-mm-dd", background="#0891B2", foreground="white", borderwidth=0)
            if value:
                try:
                    date_entry.set_date(value)
                except Exception:
                    pass
            date_entry.pack(fill="x", expand=True)
            return container, {"kind": "date", "widget": date_entry}

        if tipo == "CLICK":
            label = ctk.CTkLabel(parent, text="Clique automatico. Nenhum valor necessario.", text_color=TEXT_MUTED, justify="left")
            return label, {"kind": "static", "value": ""}

        placeholder = "numero,numero,numero" if tipo == "STRINGINT" else "Informe o valor"
        entry = ctk.CTkEntry(parent, height=32, placeholder_text=placeholder)
        if value:
            entry.insert(0, value)
        return entry, {"kind": "entry", "widget": entry}

    def _meta_value(self, meta: dict) -> str:
        if meta["kind"] == "entry":
            return meta["widget"].get().strip()
        if meta["kind"] == "date":
            return meta["widget"].get().strip()
        return str(meta.get("value", "")).strip()

    def load_data(self) -> None:
        self.set_error("")
        for child in self.reports_frame.winfo_children():
            child.destroy()
        self.filter_inputs = {}

        try:
            payload = self.backend.get_operation_reports_data(int(self.operation["id"]))
        except DesktopAppError as exc:
            self.set_error(str(exc))
            return

        relatorios_disponiveis = payload.get("relatorios_disponiveis", [])
        relatorios_operacao = payload.get("relatorios_operacao", [])
        vinculados_ids = {int(item["id_relatorio"]) for item in relatorios_operacao}
        disponiveis = [item for item in relatorios_disponiveis if int(item["id"]) not in vinculados_ids]

        self.available_reports_map = build_unique_label_map(disponiveis)
        values = list(self.available_reports_map.keys()) or ["Sem relatorios disponiveis"]
        self.report_menu.set_values(values)
        self.report_menu.set(values[0])
        self.report_menu.set_state("normal" if self.available_reports_map else "disabled")

        self.summary_label.configure(
            text=f"{len(relatorios_operacao)} relatorio(s) vinculados nesta operacao. Edite os filtros abaixo e salve por relatorio."
        )

        if not relatorios_operacao:
            ctk.CTkLabel(self.reports_frame, text="Nenhum relatorio vinculado ainda.", text_color=TEXT_MUTED).grid(
                row=0, column=0, sticky="w", padx=14, pady=14
            )
            return

        for row_index, relatorio in enumerate(relatorios_operacao):
            card = ctk.CTkFrame(self.reports_frame, fg_color=PANEL_BG, corner_radius=16)
            card.grid(row=row_index, column=0, sticky="ew", padx=10, pady=10)
            card.grid_columnconfigure((0, 1), weight=1)

            ctk.CTkLabel(card, text=relatorio["nome_relatorio"], font=ctk.CTkFont(size=16, weight="bold")).grid(
                row=0, column=0, sticky="w", padx=14, pady=(12, 4)
            )
            ctk.CTkLabel(
                card,
                text=f"Relatorio ID {relatorio['id_relatorio']}",
                text_color=TEXT_MUTED,
            ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
            ctk.CTkButton(
                card,
                text="Salvar filtros",
                width=130,
                fg_color=ACCENT,
                hover_color=ACCENT_HOVER,
                text_color=ACCENT_TEXT,
                command=lambda current=relatorio: self.save_report_filters(current),
            ).grid(row=0, column=1, sticky="e", padx=14, pady=(12, 4))
            ctk.CTkButton(
                card,
                text="Excluir vinculo",
                width=130,
                fg_color=DANGER_BG,
                hover_color=DANGER_HOVER,
                command=lambda current=relatorio: self.remove_report(current),
            ).grid(row=1, column=1, sticky="e", padx=14, pady=(0, 8))

            filtros = relatorio.get("filtros", [])
            if not filtros:
                ctk.CTkLabel(card, text="Este relatorio nao possui filtros vinculados.", text_color=TEXT_MUTED).grid(
                    row=2, column=0, columnspan=2, sticky="w", padx=14, pady=(0, 12)
                )
                continue

            for filter_index, filtro in enumerate(filtros):
                col = filter_index % 2
                grid_row = 2 + (filter_index // 2)
                field = ctk.CTkFrame(card, fg_color=SUBPANEL_BG, corner_radius=12)
                field.grid(row=grid_row, column=col, sticky="ew", padx=14, pady=(6, 6))
                field.grid_columnconfigure(0, weight=1)

                ctk.CTkLabel(field, text=filtro["nome_filtro"], anchor="w", font=ctk.CTkFont(size=13, weight="bold")).grid(
                    row=0, column=0, sticky="ew", padx=12, pady=(10, 4)
                )
                widget, meta = self._build_value_widget(field, str(filtro.get("valor") or ""), filtro.get("tipo_campo_valor", ""))
                widget.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
                self.filter_inputs[(int(relatorio["id_relatorio"]), int(filtro["id_filtro"]))] = meta

    def add_report(self) -> None:
        selected = self.available_reports_map.get(self.report_menu.get())
        if not selected:
            return
        try:
            message = self.backend.add_report_to_operation(int(self.operation["id"]), int(selected["id"]))
        except DesktopAppError as exc:
            self.set_error(str(exc))
            return
        self.summary_label.configure(text=message, text_color=SUCCESS_TEXT)
        self.load_data()

    def save_report_filters(self, relatorio: dict) -> None:
        filtros = []
        for filtro in relatorio.get("filtros", []):
            key = (int(relatorio["id_relatorio"]), int(filtro["id_filtro"]))
            meta = self.filter_inputs.get(key)
            if meta is None:
                continue
            filtros.append((int(filtro["id_filtro"]), self._meta_value(meta)))

        try:
            message = self.backend.update_operation_report_filters(
                int(self.operation["id"]),
                int(relatorio["id_relatorio"]),
                filtros,
            )
        except DesktopAppError as exc:
            self.set_error(str(exc))
            return
        self.summary_label.configure(text=message, text_color=SUCCESS_TEXT)

    def remove_report(self, relatorio: dict) -> None:
        if not messagebox.askyesno(
            "Relatorios da Operacao",
            f"Excluir o vinculo do relatorio '{relatorio['nome_relatorio']}' desta operacao?",
        ):
            return
        try:
            message = self.backend.remove_report_from_operation(
                int(self.operation["id"]),
                int(relatorio["id_relatorio"]),
            )
        except DesktopAppError as exc:
            self.set_error(str(exc))
            return
        self.summary_label.configure(text=message, text_color=SUCCESS_TEXT)
        self.load_data()


class UsersView(GridView):
    def __init__(self, master: "ShellFrame", backend: DesktopBackend) -> None:
        super().__init__(master, "Usuarios")
        self.backend = backend
        self.search_entry = ctk.CTkEntry(self.toolbar, placeholder_text="Buscar por login, email ou area", width=320)
        self.search_entry.pack(side="left", padx=(0, 10))
        self.status_menu = SearchableComboBox(self.toolbar, ["ativos", "inativos", "todos"], width=18)
        self.status_menu.pack(side="left", padx=(0, 10))
        self.status_menu.set("ativos")
        ctk.CTkButton(self.toolbar, text="Novo", command=self.open_create).pack(side="left", padx=(0, 8))
        ctk.CTkButton(self.toolbar, text="Editar", command=self.open_edit).pack(side="left", padx=(0, 8))
        ctk.CTkButton(self.toolbar, text="Inativar", fg_color=DANGER_BG, hover_color=DANGER_HOVER, command=self.deactivate_selected).pack(side="left", padx=(0, 8))
        ctk.CTkButton(self.toolbar, text="Atualizar", command=self.load_data).pack(side="left")

        self.rows_by_id: dict[int, dict] = {}
        columns = ("id", "login", "email", "area", "perfil", "status")
        self.tree.configure(columns=columns)
        for column, title, width in (
            ("id", "ID", 70),
            ("login", "Login", 180),
            ("email", "Email", 240),
            ("area", "Area", 160),
            ("perfil", "Perfil", 180),
            ("status", "Status", 110),
        ):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, anchor="w")

    def load_data(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            rows = self.backend.list_users(self.search_entry.get().strip(), self.status_menu.get())
        except DesktopAppError as exc:
            self.message_label.configure(text=str(exc), text_color=ERROR_TEXT)
            return
        self.rows_by_id = {int(row["id"]): row for row in rows}
        for row in rows:
            self.tree.insert("", "end", values=(row["id"], row["login"], row["email"], row["area"], row["perfil"], row["status"]))
        self.message_label.configure(text=f"{len(rows)} usuario(s) carregado(s).", text_color=TEXT_MUTED)

    def _selected_user(self) -> dict | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Usuarios", "Selecione um usuario.")
            return None
        values = self.tree.item(selected[0], "values")
        return self.rows_by_id.get(int(values[0]))

    def open_create(self) -> None:
        UserDialog(self, self.backend, self.load_data)

    def open_edit(self) -> None:
        user = self._selected_user()
        if not user:
            return
        UserDialog(self, self.backend, self.load_data, user=user)

    def deactivate_selected(self) -> None:
        user = self._selected_user()
        if not user:
            return
        if not messagebox.askyesno("Usuarios", f"Inativar o usuario {user['login']}?"):
            return
        try:
            message = self.backend.deactivate_user(int(user["id"]))
        except DesktopAppError as exc:
            self.message_label.configure(text=str(exc), text_color=ERROR_TEXT)
            return
        self.load_data()
        self.message_label.configure(text=message, text_color=SUCCESS_TEXT)


class LogsView(GridView):
    def __init__(self, master: "ShellFrame", backend: DesktopBackend) -> None:
        super().__init__(master, "Logs")
        self.backend = backend

        values = ["operacao"]
        if backend.current_user and backend.current_user["access_id"] == 1:
            values.insert(0, "adm")

        self.kind_menu = SearchableComboBox(self.toolbar, values, width=14)
        self.kind_menu.pack(side="left", padx=(0, 10))
        self.kind_menu.set(values[0])
        self.filter_entry = ctk.CTkEntry(self.toolbar, placeholder_text="Filtro principal", width=280)
        self.filter_entry.pack(side="left", padx=(0, 10))
        ctk.CTkButton(self.toolbar, text="Atualizar", command=self.load_data).pack(side="left")

        self.tree.configure(columns=("col1", "col2", "col3", "col4", "col5"))

    def load_data(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        aba = self.kind_menu.get()
        if aba == "adm":
            filtros = {
                "usuario": self.filter_entry.get().strip(),
                "tipo_evento": "",
                "data_inicio": "",
                "data_fim": "",
            }
            columns = (
                ("col1", "Usuario", 150),
                ("col2", "Evento", 150),
                ("col3", "Detalhe", 420),
                ("col4", "Data", 180),
                ("col5", "Payload", 80),
            )
        else:
            filtros = {
                "nome_operacao": self.filter_entry.get().strip(),
                "status": "",
                "responsavel": "",
                "data_inicio": "",
            }
            columns = (
                ("col1", "Tipo", 120),
                ("col2", "Operacao", 220),
                ("col3", "Relatorio", 260),
                ("col4", "Status", 120),
                ("col5", "Atualizacao", 180),
            )

        self.tree.configure(columns=[name for name, _, _ in columns])
        for name, title, width in columns:
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, anchor="w")

        try:
            rows = self.backend.list_logs(aba=aba, filtros=filtros)
        except DesktopAppError as exc:
            self.message_label.configure(text=str(exc), text_color=ERROR_TEXT)
            return

        for row in rows[:200]:
            if aba == "adm":
                values = (row["usuario"], row["evento"], row["detalhe"], row["data_evento"], "sim" if row["payload_json"] else "nao")
            else:
                values = (row["tipo_execucao"], row["nome_operacao"], row["nome_relatorio"], row["status"], row["atualizacao"])
            self.tree.insert("", "end", values=values)

        self.message_label.configure(text=f"{len(rows)} registro(s) carregado(s).", text_color=TEXT_MUTED)


class OperationsView(GridView):
    def __init__(self, master: "ShellFrame", backend: DesktopBackend) -> None:
        super().__init__(master, "Operacoes")
        self.backend = backend
        self.search_entry = ctk.CTkEntry(self.toolbar, placeholder_text="Buscar operacao", width=320)
        self.search_entry.pack(side="left", padx=(0, 10))
        ctk.CTkButton(self.toolbar, text="Nova", command=self.open_create).pack(side="left", padx=(0, 8))
        ctk.CTkButton(self.toolbar, text="Editar", command=self.open_edit).pack(side="left", padx=(0, 8))
        ctk.CTkButton(self.toolbar, text="Relatorios", command=self.open_reports).pack(side="left", padx=(0, 8))
        ctk.CTkButton(self.toolbar, text="Inativar", fg_color=DANGER_BG, hover_color=DANGER_HOVER, command=self.deactivate_selected).pack(side="left", padx=(0, 8))
        ctk.CTkButton(self.toolbar, text="Atualizar", command=self.load_data).pack(side="left")

        self.rows_by_id: dict[int, dict] = {}
        columns = ("id", "nome", "status", "data")
        self.tree.configure(columns=columns)
        for column, title, width in (
            ("id", "ID", 80),
            ("nome", "Nome", 320),
            ("status", "Status", 110),
            ("data", "Criacao", 180),
        ):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, anchor="w")

    def load_data(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            rows = self.backend.list_operacoes(self.search_entry.get().strip())
        except DesktopAppError as exc:
            self.message_label.configure(text=str(exc), text_color=ERROR_TEXT)
            return
        self.rows_by_id = {int(row["id"]): row for row in rows}
        for row in rows:
            self.tree.insert("", "end", values=(row["id"], row["nome"], row["status"], row["data_criacao"]))
        self.message_label.configure(text=f"{len(rows)} operacao(oes) carregada(s).", text_color=TEXT_MUTED)

    def _selected_operation(self) -> dict | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Operacoes", "Selecione uma operacao.")
            return None
        values = self.tree.item(selected[0], "values")
        return self.rows_by_id.get(int(values[0]))

    def open_create(self) -> None:
        OperationDialog(self, self.backend, self.load_data)

    def open_edit(self) -> None:
        operation = self._selected_operation()
        if not operation:
            return
        OperationDialog(self, self.backend, self.load_data, operation=operation)

    def deactivate_selected(self) -> None:
        operation = self._selected_operation()
        if not operation:
            return
        if not messagebox.askyesno("Operacoes", f"Inativar a operacao {operation['nome']}?"):
            return
        try:
            message = self.backend.deactivate_operation(int(operation["id"]))
        except DesktopAppError as exc:
            self.message_label.configure(text=str(exc), text_color=ERROR_TEXT)
            return
        self.load_data()
        self.message_label.configure(text=message, text_color=SUCCESS_TEXT)

    def open_reports(self) -> None:
        operation = self._selected_operation()
        if not operation:
            return
        OperationReportsDialog(self, self.backend, operation)


class ShellFrame(ctk.CTkFrame):
    def __init__(self, master: "DesktopApplication", user: dict) -> None:
        super().__init__(master, fg_color=APP_BG)
        self.master = master
        self.backend = master.backend
        self.user = user
        self.current_view = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=SIDEBAR_BG)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(sidebar, text="DataExtract EBM", font=ctk.CTkFont(size=24, weight="bold")).pack(
            anchor="w", padx=20, pady=(24, 6)
        )
        ctk.CTkLabel(
            sidebar,
            text=f"{user['login']}  |  {ACCESS_LABELS.get(user['access_id'], 'Perfil')}",
            text_color=TEXT_MUTED,
            wraplength=180,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 24))

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew")

        self.views = {
            "automacao": AutomationView(self, self.backend),
            "perfil": ProfileView(self, self.backend),
        }

        buttons = [("Automacao", "automacao"), ("Perfil", "perfil")]
        if user["access_id"] in {1, 2}:
            self.views["operacoes"] = OperationsView(self, self.backend)
            self.views["logs"] = LogsView(self, self.backend)
            buttons.extend([("Operacoes", "operacoes"), ("Logs", "logs")])
        if user["access_id"] == 1:
            self.views["usuarios"] = UsersView(self, self.backend)
            buttons.insert(2, ("Usuarios", "usuarios"))

        for text, key in buttons:
            SidebarButton(sidebar, text, lambda current=key: self.show_view(current)).pack(fill="x", padx=14, pady=6)

        ctk.CTkButton(
            sidebar,
            text="Sair",
            fg_color=DANGER_BG,
            hover_color=DANGER_HOVER,
            command=self.logout,
        ).pack(side="bottom", fill="x", padx=14, pady=18)

        self.show_view("automacao")

    def show_view(self, key: str) -> None:
        if self.current_view:
            self.current_view.pack_forget()
        view = self.views[key]
        view.pack(fill="both", expand=True)
        load_data = getattr(view, "load_data", None)
        if callable(load_data):
            try:
                load_data()
            except DesktopPermissionError:
                pass
        self.current_view = view

    def logout(self) -> None:
        self.backend.logout()
        self.master.show_login()


class DesktopApplication(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.backend = DesktopBackend()
        self._logo_cache: dict[tuple[int, int], tk.PhotoImage] = {}
        self.title("AppCaptacao")
        self.geometry("1280x760")
        self.minsize(1120, 640)
        self.configure(fg_color=APP_BG)
        self._configure_combobox_style()
        self._active_frame: ctk.CTkFrame | None = None
        self.show_login()

    def _configure_combobox_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "AppCaptacao.TCombobox",
            fieldbackground=PANEL_BG,
            background=PANEL_BG,
            foreground=TEXT_STRONG,
            borderwidth=0,
            relief="flat",
            arrowsize=16,
            padding=(8, 6, 28, 6),
            insertcolor=TEXT_STRONG,
        )
        style.map(
            "AppCaptacao.TCombobox",
            fieldbackground=[("readonly", PANEL_BG), ("disabled", "#F1F5F9")],
            foreground=[("disabled", TEXT_MUTED)],
            selectbackground=[("focus", PANEL_BG)],
            selectforeground=[("focus", TEXT_STRONG)],
        )

    def load_logo(self, size: tuple[int, int]) -> tk.PhotoImage | None:
        if size in self._logo_cache:
            return self._logo_cache[size]

        logo_path = get_bundle_base_dir() / "project" / "static" / "img" / "ebm.png"
        if not logo_path.exists():
            return None

        image = tk.PhotoImage(file=str(logo_path))
        original_width = max(image.width(), 1)
        original_height = max(image.height(), 1)
        scale_x = max(round(original_width / max(size[0], 1)), 1)
        scale_y = max(round(original_height / max(size[1], 1)), 1)
        image = image.subsample(scale_x, scale_y)
        self._logo_cache[size] = image
        return image

    def _swap_frame(self, frame: ctk.CTkFrame) -> None:
        if self._active_frame is not None:
            self._active_frame.destroy()
        self._active_frame = frame
        frame.pack(fill="both", expand=True)

    def show_login(self) -> None:
        self._swap_frame(LoginFrame(self))

    def show_shell(self, user: dict) -> None:
        self._swap_frame(ShellFrame(self, user))


def main() -> None:
    loaded_config_path = initialize_environment()
    if loaded_config_path is None:
        raise RuntimeError(
            "Configuracao nao encontrada. "
            "Para esta fase de testes, crie um arquivo .env ao lado do executavel com as variaveis da aplicacao. "
            f"Caminho sugerido: {get_runtime_env_path()}."
        )

    app = DesktopApplication()
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(0, str(exc), "AppCaptacao", 0x10)
        else:
            raise
