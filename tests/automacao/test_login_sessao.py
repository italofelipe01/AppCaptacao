import unittest
from unittest.mock import MagicMock, patch

from selenium.common.exceptions import WebDriverException

from app_captacao.automacao import config, login, navegador, sessao


class LoginTests(unittest.TestCase):
    def test_login_delegates_to_automatic_flow(self):
        driver = MagicMock()
        wait = MagicMock()
        with patch.object(sessao, "restaurar_sessao_sienge", return_value=True) as restaurar, patch.object(
            login, "_fazer_login_automatico"
        ) as login_automatico:
            login.fazer_login(driver, wait, "usuario@example.com", "senha")

        # Decisao registrada: a sessao salva nao e restaurada; o login e sempre automatico.
        restaurar.assert_not_called()
        self.assertFalse(hasattr(login, "restaurar_sessao_sienge"))
        login_automatico.assert_called_once_with(driver, wait, "usuario@example.com", "senha")

    def test_sso_frame_detach_falls_back_to_manual_token(self):
        driver = MagicMock()
        wait = MagicMock()
        with patch.object(
            login,
            "_fazer_login_automatico",
            side_effect=WebDriverException("target frame detached"),
        ), patch.object(login, "_aguardar_autenticacao_interativa", return_value=True) as aguardar, patch.object(
            sessao, "salvar_sessao_sienge"
        ) as salvar, patch.object(login, "SESSION_REUSE_ENABLED", True):
            login.fazer_login(driver, wait, "usuario@example.com", "senha")

        aguardar.assert_called_once_with(driver, login.INTERACTIVE_LOGIN_TIMEOUT)
        salvar.assert_called_once_with(driver, "usuario@example.com")


class SessionStateTests(unittest.TestCase):
    def test_session_is_not_active_while_login_control_is_visible(self):
        driver = MagicMock()
        driver.current_window_handle = "tab-2"
        driver.window_handles = ["tab-1", "tab-2"]
        driver.current_url = config.LOGIN_URL
        driver.execute_script.return_value = "complete"
        driver.find_elements.side_effect = lambda by, value: [object()] if value == "btnEntrarComSiengeID" else []

        self.assertFalse(sessao.sessao_sienge_ativa(driver))

    def test_session_is_active_only_on_loaded_sienge_page_without_login_controls(self):
        driver = MagicMock()
        driver.current_window_handle = "tab-2"
        driver.window_handles = ["tab-1", "tab-2"]
        driver.current_url = "https://ebm.sienge.com.br/sienge/8/index.html"
        driver.execute_script.return_value = "complete"
        driver.find_elements.return_value = []

        self.assertTrue(sessao.sessao_sienge_ativa(driver))


class BrowserSelectionTests(unittest.TestCase):
    def test_edge_failure_does_not_fall_back_to_chrome(self):
        with patch.object(navegador, "SELENIUM_BROWSER", "edge"), patch.object(
            navegador,
            "_criar_driver_edge",
            side_effect=RuntimeError("perfil Edge indisponivel"),
        ), patch.object(navegador, "_criar_driver_chrome") as criar_chrome, patch.object(navegador.Path, "mkdir"):
            with self.assertRaisesRegex(RuntimeError, "perfil Edge indisponivel"):
                navegador.criar_driver()

        criar_chrome.assert_not_called()


if __name__ == "__main__":
    unittest.main()
