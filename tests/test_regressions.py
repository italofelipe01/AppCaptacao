import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app_core import app as app_module
from services import automacao_service


class _FakeCursor:
    def __init__(self, statements):
        self.statements = statements

    def execute(self, query, params=()):
        self.statements.append((" ".join(query.split()), tuple(params)))
        return self


class _FakeConnection:
    def __init__(self):
        self.statements = []
        self.committed = False

    def cursor(self):
        return _FakeCursor(self.statements)

    def commit(self):
        self.committed = True

    def close(self):
        pass


class _FakeDriver:
    def __init__(self):
        self.closed = False

    def quit(self):
        self.closed = True


class OperationCreationTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app_module.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["user_login"] = "tester"
            session["user_access_id"] = 1

    def _request_patches(self):
        return patch.multiple(
            app_module,
            _safe_db_call=lambda loader, default: default,
            _log_config=lambda *args, **kwargs: None,
        )

    def test_rejects_operation_without_reports(self):
        with self._request_patches():
            response = self.client.post(
                "/acompanhamento/operacoes",
                data={"nome_operacao": "Operacao sem itens"},
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            messages = [message for _, message in session.get("_flashes", [])]
        self.assertTrue(any("pelo menos um relatorio" in message for message in messages))

    def test_creates_operation_and_links_in_submitted_order(self):
        connection = _FakeConnection()
        linked = []

        def insert_link(_connection, operation_id, report_id):
            linked.append((operation_id, report_id))

        with self._request_patches(), patch.object(app_module, "_db_connection", return_value=connection), patch.object(
            app_module, "_operation_name_exists", return_value=False
        ), patch.object(app_module, "_get_next_id", return_value=42), patch.object(
            app_module, "_column_exists", return_value=False
        ), patch.object(app_module, "_insert_operation_report_link", side_effect=insert_link):
            response = self.client.post(
                "/acompanhamento/operacoes",
                data={"nome_operacao": "Fechamento mensal", "id_relatorio": ["7", "2", "5"]},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(connection.committed)
        self.assertEqual(linked, [(42, 7), (42, 2), (42, 5)])
        self.assertIn("IdCapRecursoOperacoes", connection.statements[0][0])
        self.assertEqual(connection.statements[0][1][:2], (42, "Fechamento mensal"))

    def test_rejects_duplicate_active_name(self):
        connection = _FakeConnection()
        with self._request_patches(), patch.object(app_module, "_db_connection", return_value=connection), patch.object(
            app_module, "_operation_name_exists", return_value=True
        ):
            response = self.client.post(
                "/acompanhamento/operacoes",
                data={"nome_operacao": "Duplicada", "id_relatorio": "1"},
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(connection.committed)

    def test_operation_payload_uses_link_order(self):
        captured = []

        def fake_fetch_all(query, params=()):
            captured.append(" ".join(query.split()))
            return []

        with patch.object(app_module, "_fetch_all", side_effect=fake_fetch_all), patch.object(
            app_module, "_db_connection", return_value=_FakeConnection()
        ), patch.object(app_module, "_get_filter_value_column", return_value=None), patch.object(
            app_module, "_column_exists", return_value=False
        ):
            self.assertEqual(app_module._load_relatorio_operacao_payload(9), [])
        self.assertIn("ORDER BY rxo.IdCapRecursoRelatorioOperacao", captured[0])


class ExecutionResultTests(unittest.TestCase):
    def test_sequence_reports_partial_success_per_report(self):
        driver = _FakeDriver()
        reports = [
            {"id": 1, "nome": "Relatorio A", "operacao_nome": "Operacao X"},
            {"id": 2, "nome": "Relatorio B", "operacao_nome": "Operacao X"},
        ]

        def execute(_driver, _wait, report):
            if report["id"] == 2:
                raise automacao_service.DownloadProcessingError("copia", "Destino indisponivel")
            return [r"C:\Destino\Relatorio_A.xlsx"]

        with patch.object(automacao_service, "_criar_driver", return_value=driver), patch.object(
            automacao_service, "_fazer_login"
        ), patch.object(automacao_service, "_executar_relatorio_no_driver", side_effect=execute), patch.object(
            automacao_service, "_aguardar_pasta_download_estabilizar", return_value=True
        ), patch.object(automacao_service.time, "sleep"):
            result = automacao_service.executar_relatorios_em_sequencia("user", "password", reports)

        self.assertEqual(result["quantidade_baixados"], 1)
        self.assertEqual(result["quantidade_nao_baixados"], 1)
        self.assertEqual([item["estado"] for item in result["itens"]], ["baixado", "nao_baixado"])
        self.assertEqual(result["falhas"][0]["relatorio_nome"], "Relatorio B")
        self.assertEqual(result["falhas"][0]["etapa"], "copia")

    def test_authentication_failure_marks_all_reports_ignored(self):
        reports = [{"id": 1, "nome": "A"}, {"id": 2, "nome": "B"}]
        with patch.object(automacao_service, "_criar_driver", return_value=_FakeDriver()), patch.object(
            automacao_service, "_fazer_login", side_effect=RuntimeError("MFA pendente")
        ):
            result = automacao_service.executar_relatorios_em_sequencia("user", "password", reports)
        self.assertEqual([item["estado"] for item in result["itens"]], ["ignorado", "ignorado"])
        self.assertEqual(result["quantidade_nao_baixados"], 2)

    def test_download_watcher_does_not_reuse_preexisting_file(self):
        directory = Path(__file__).parent
        old_file = directory / f"relatorio_antigo_{uuid.uuid4().hex}.xlsx"
        try:
            old_file.write_bytes(b"old")
            with patch.object(automacao_service, "DOWNLOAD_DIR", str(directory)), patch.object(
                automacao_service, "DOWNLOAD_WAIT_TIMEOUT", 0.08
            ), patch.object(automacao_service, "DOWNLOAD_STABLE_CHECK_INTERVAL", 0.01):
                marker = automacao_service._marcar_inicio_download()
                result = automacao_service._aguardar_arquivo_download(marker)
        finally:
            old_file.unlink(missing_ok=True)
        self.assertEqual(result, "")

    def test_download_watcher_accepts_only_a_new_stable_file(self):
        directory = Path(__file__).parent
        new_file = directory / f"novo_{uuid.uuid4().hex}.xlsx"
        try:
            with patch.object(automacao_service, "DOWNLOAD_DIR", str(directory)), patch.object(
                automacao_service, "DOWNLOAD_WAIT_TIMEOUT", 0.3
            ), patch.object(automacao_service, "DOWNLOAD_STABLE_CHECK_INTERVAL", 0.01), patch.object(
                automacao_service, "DOWNLOAD_STABLE_CYCLES_REQUIRED", 2
            ):
                marker = automacao_service._marcar_inicio_download()
                time.sleep(0.002)
                new_file.write_bytes(b"complete")
                result = automacao_service._aguardar_arquivo_download(marker)
        finally:
            new_file.unlink(missing_ok=True)
        self.assertEqual(result, new_file)


if __name__ == "__main__":
    unittest.main()
