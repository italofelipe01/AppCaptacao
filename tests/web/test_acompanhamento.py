import unittest
from unittest.mock import patch

from app_captacao.app import app
from app_captacao.catalogo import operacao_relatorios, operacoes
from app_captacao.core.database import sql
from app_captacao.core.persistence import usuarios
from app_captacao.web import auditoria
from tests.fakes import FakeConnection


class OperationCreationTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["user_login"] = "tester"
            session["user_access_id"] = 1

    def _request_patches(self):
        # Banco indisponivel para carregar o usuario: a sessao assinada vale como fallback.
        return patch.object(
            usuarios, "load_user_by_id", side_effect=RuntimeError("banco indisponivel")
        ), patch.object(auditoria, "log_config", lambda *args, **kwargs: None)

    def test_rejects_operation_without_reports(self):
        db_patch, log_patch = self._request_patches()
        with db_patch, log_patch:
            response = self.client.post(
                "/acompanhamento/operacoes",
                data={"nome_operacao": "Operacao sem itens"},
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            messages = [message for _, message in session.get("_flashes", [])]
        self.assertTrue(any("pelo menos um relatório" in message for message in messages))

    def test_creates_operation_and_links_in_submitted_order(self):
        connection = FakeConnection()
        linked = []

        def insert_link(_connection, operation_id, report_id, _usuario_id=None):
            linked.append((operation_id, report_id))

        db_patch, log_patch = self._request_patches()
        with db_patch, log_patch, patch.object(sql, "db_connection", return_value=connection), patch.object(
            operacoes, "operation_name_exists", return_value=False
        ), patch.object(sql, "get_next_id", return_value=42), patch.object(
            sql, "column_exists", return_value=False
        ), patch.object(operacao_relatorios, "insert_operation_report_link", side_effect=insert_link):
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
        connection = FakeConnection()
        db_patch, log_patch = self._request_patches()
        with db_patch, log_patch, patch.object(sql, "db_connection", return_value=connection), patch.object(
            operacoes, "operation_name_exists", return_value=True
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

        with patch.object(sql, "fetch_all", side_effect=fake_fetch_all), patch.object(
            sql, "db_connection", return_value=FakeConnection()
        ), patch.object(operacao_relatorios, "get_filter_value_column", return_value=None), patch.object(
            sql, "column_exists", return_value=False
        ):
            self.assertEqual(operacao_relatorios.load_relatorio_operacao_payload(9), [])
        self.assertIn("ORDER BY rxo.IdCapRecursoRelatorioOperacao", captured[0])


if __name__ == "__main__":
    unittest.main()
