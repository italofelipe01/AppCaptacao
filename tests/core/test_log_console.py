import io
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_captacao.core.shared import log_tecnico


class LogConsoleTests(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        with patch.object(log_tecnico, "pasta_de_logs", return_value=Path(pasta.name)):
            self.arquivo = log_tecnico.configurar_log_tecnico(console=True)
        self.addCleanup(log_tecnico.desligar_log_tecnico)

        self.console = io.StringIO()
        for handler in log_tecnico._handlers:
            if type(handler) is logging.StreamHandler:
                handler.setStream(self.console)

        # Como o waitress faz com logging.basicConfig(): um handler na raiz.
        self.raiz = io.StringIO()
        handler_raiz = logging.StreamHandler(self.raiz)
        logging.getLogger().addHandler(handler_raiz)
        self.addCleanup(logging.getLogger().removeHandler, handler_raiz)

    def _registrar_erro(self):
        try:
            raise RuntimeError("Message: unknown error: failed to close window in 20 seconds\nStacktrace:\n(No symbol)")
        except RuntimeError:
            logging.getLogger("app_captacao.automacao.execucao").exception("Erro no relatorio 17.")

    def test_console_mostra_o_erro_em_uma_linha(self):
        self._registrar_erro()
        linhas = [linha for linha in self.console.getvalue().splitlines() if linha.strip()]
        self.assertEqual(len(linhas), 1, linhas)
        self.assertIn("[ERRO ] Erro no relatorio 17. (RuntimeError: unknown error: failed to close window", linhas[0])

    def test_linha_nao_sai_duplicada_pela_raiz(self):
        self._registrar_erro()
        self.assertEqual(self.raiz.getvalue(), "")

    def test_arquivo_guarda_o_traceback_completo(self):
        self._registrar_erro()
        for handler in log_tecnico._handlers:
            handler.flush()
        self.assertIn("Traceback", self.arquivo.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
