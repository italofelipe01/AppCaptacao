import importlib
import sys
import types
import unittest
from unittest.mock import patch


def _importar_desktop_sem_customtkinter():
    falso = types.ModuleType("customtkinter")
    falso.CTk = object
    falso.set_appearance_mode = lambda *args, **kwargs: None
    falso.set_default_color_theme = lambda *args, **kwargs: None
    with patch.dict(sys.modules, {"customtkinter": falso}):
        sys.modules.pop("app_captacao.desktop.desktop_app", None)
        return importlib.import_module("app_captacao.desktop.desktop_app")


class DesktopAppTests(unittest.TestCase):
    def test_servidor_iniciado_pela_janela_nao_abre_um_segundo_navegador(self):
        desktop_app = _importar_desktop_sem_customtkinter()
        janela = types.SimpleNamespace(server_started_by_app=False, after=lambda *args: None)
        with patch.object(desktop_app, "run_application") as run_application:
            desktop_app.AppCaptacaoDesktop._run_server(janela)
        run_application.assert_called_once_with(use_waitress=True, open_browser=False)
        self.assertTrue(janela.server_started_by_app)


if __name__ == "__main__":
    unittest.main()
