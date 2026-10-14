import unittest
from unittest.mock import patch

from selenium.common.exceptions import TimeoutException

from app_captacao.automacao import downloads, erros, execucao, login, navegador


class _FakeDriver:
    def __init__(self):
        self.closed = False

    def quit(self):
        self.closed = True


class ExecutionErrorMessageTests(unittest.TestCase):
    def test_remove_stacktrace_do_webdriver_da_mensagem_visivel(self):
        erro = TimeoutException("Message: campo indisponivel\nStacktrace:\nmsedgedriver!GetHandleVerifier")
        mensagem = erros.mensagem_erro_usuario(erro)
        self.assertEqual(mensagem, "campo indisponivel")
        self.assertNotIn("Stacktrace", mensagem)

    def test_timeout_sem_mensagem_recebe_texto_amigavel(self):
        mensagem = erros.mensagem_erro_usuario(TimeoutException())
        self.assertIn("Tempo esgotado", mensagem)


class SequenceExecutionTests(unittest.TestCase):
    def test_sequence_reports_partial_success_per_report(self):
        driver = _FakeDriver()
        reports = [
            {"id": 1, "nome": "Relatorio A", "operacao_nome": "Operacao X"},
            {"id": 2, "nome": "Relatorio B", "operacao_nome": "Operacao X"},
        ]

        def execute(_driver, _wait, report):
            if report["id"] == 2:
                raise erros.DownloadProcessingError("copia", "Destino indisponivel")
            return [r"C:\Destino\Relatorio_A.xlsx"]

        with patch.object(navegador, "criar_driver", return_value=driver), patch.object(
            login, "fazer_login"
        ), patch.object(execucao, "_executar_relatorio_no_driver", side_effect=execute), patch.object(
            downloads, "aguardar_pasta_download_estabilizar", return_value=True
        ), patch.object(execucao.time, "sleep"):
            result = execucao.executar_relatorios_em_sequencia("user", "password", reports)

        self.assertEqual(result["quantidade_baixados"], 1)
        self.assertEqual(result["quantidade_nao_baixados"], 1)
        self.assertEqual([item["estado"] for item in result["itens"]], ["baixado", "nao_baixado"])
        self.assertEqual(result["falhas"][0]["relatorio_nome"], "Relatorio B")
        self.assertEqual(result["falhas"][0]["etapa"], "copia")

    def test_authentication_failure_marks_all_reports_ignored(self):
        reports = [{"id": 1, "nome": "A"}, {"id": 2, "nome": "B"}]
        with patch.object(navegador, "criar_driver", return_value=_FakeDriver()), patch.object(
            login, "fazer_login", side_effect=RuntimeError("MFA pendente")
        ):
            result = execucao.executar_relatorios_em_sequencia("user", "password", reports)
        self.assertEqual([item["estado"] for item in result["itens"]], ["ignorado", "ignorado"])
        self.assertEqual(result["quantidade_nao_baixados"], 2)


if __name__ == "__main__":
    unittest.main()
