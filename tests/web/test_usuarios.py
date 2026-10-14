import unittest
from unittest.mock import patch

from app_captacao.app import app
from app_captacao.core.database import sql
from app_captacao.core.persistence import usuarios
from app_captacao.web import auditoria
from tests.fakes import FakeConnection

ADMIN_ROW = {
    "id": 10,
    "login": "admin",
    "email": "admin@example.com",
    "area": "ti",
    "access_id": 1,
    "ativo": 1,
    "data_criacao": None,
}


class UserManagementTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["user_login"] = "admin"
            session["user_access_id"] = 1

    def test_user_listing_does_not_depend_on_access_table_column_names(self):
        captured = []

        def fake_fetch_all(query, params=()):
            captured.append(" ".join(query.split()))
            return [
                {
                    "id": 4,
                    "login": "operador",
                    "email": "operador@example.com",
                    "area": "captacao",
                    "access_id": 2,
                    "ativo": 1,
                    "data_criacao": None,
                }
            ]

        with patch.object(sql, "fetch_all", side_effect=fake_fetch_all):
            users = usuarios.load_usuarios("", "ativos")

        self.assertNotIn("CapRecursoAcesso", captured[0])
        self.assertEqual(users[0]["id_acesso"], 2)
        self.assertEqual(users[0]["perfil"], "Usuario com cadastro de operacao")

    def test_user_page_renders_responsive_modals(self):
        with patch.object(usuarios, "load_user_by_id", return_value=ADMIN_ROW), patch.object(
            usuarios, "load_usuarios", return_value=[]
        ):
            response = self.client.get("/usuarios")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"app-modal-overlay", response.data)
        self.assertIn(b"app-modal-body", response.data)

    def test_creates_user_with_explicit_id(self):
        connection = FakeConnection()
        with patch.object(usuarios, "load_user_by_id", return_value=ADMIN_ROW), patch.object(
            sql, "db_connection", return_value=connection
        ), patch.object(usuarios, "user_duplicate_field", return_value=None), patch.object(
            sql, "column_is_identity", return_value=False
        ), patch.object(sql, "get_next_id", return_value=21), patch.object(auditoria, "log_config"):
            response = self.client.post(
                "/usuarios",
                data={
                    "login_usuario": "novo.usuario",
                    "email": "novo@example.com",
                    "area": "captacao",
                    "id_acesso": "3",
                    "senha": "senha-segura",
                    "confirmar_senha": "senha-segura",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(connection.committed)
        self.assertIn("IdLogin", connection.statements[0][0])
        self.assertEqual(connection.statements[0][1][0], 21)

    def test_rejects_duplicate_user_without_committing(self):
        connection = FakeConnection()
        with patch.object(usuarios, "load_user_by_id", return_value=ADMIN_ROW), patch.object(
            sql, "db_connection", return_value=connection
        ), patch.object(usuarios, "user_duplicate_field", return_value="login"):
            response = self.client.post(
                "/usuarios",
                data={
                    "login_usuario": "existente",
                    "email": "novo@example.com",
                    "area": "captacao",
                    "id_acesso": "3",
                    "senha": "senha-segura",
                    "confirmar_senha": "senha-segura",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(connection.committed)

    def test_rejects_user_without_password(self):
        with patch.object(usuarios, "load_user_by_id", return_value=ADMIN_ROW):
            response = self.client.post(
                "/usuarios",
                data={
                    "login_usuario": "novo.usuario",
                    "email": "novo@example.com",
                    "area": "captacao",
                    "id_acesso": "3",
                    "senha": "",
                    "confirmar_senha": "",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            messages = [message for _, message in session.get("_flashes", [])]
        self.assertTrue(any("obrigatorios" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
