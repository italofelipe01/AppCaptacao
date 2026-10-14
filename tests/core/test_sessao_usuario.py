import os
import unittest
from unittest.mock import Mock, patch

from werkzeug.security import generate_password_hash

from app_captacao.app import app
from app_captacao.core.persistence import usuarios
from app_captacao.core.security import auth

USUARIO_ATIVO = {"id": 10, "login": "ana", "email": "ana@example.com", "area": "cap", "access_id": 1, "ativo": 1, "data_criacao": None}


class SessaoUsuarioTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["user_login"] = "ana"
            session["user_access_id"] = 1

    def test_usuario_inativado_perde_acesso_na_proxima_requisicao(self):
        with patch.object(usuarios, "load_user_by_id", return_value={**USUARIO_ATIVO, "ativo": 0}):
            response = self.client.get("/perfil")
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn("user_login", session)

    def test_usuario_excluido_perde_acesso(self):
        with patch.object(usuarios, "load_user_by_id", return_value=None):
            response = self.client.get("/perfil")
        self.assertEqual(response.status_code, 302)

    def test_perfil_vem_do_banco_e_nao_da_sessao(self):
        with self.client.session_transaction() as session:
            session["user_access_id"] = 1
        rebaixado = {**USUARIO_ATIVO, "access_id": 3}
        with patch.object(usuarios, "load_user_by_id", return_value=rebaixado):
            response = self.client.get("/usuarios")
        # Perfil 3 nao administra usuarios: e mandado para o proprio perfil.
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/perfil"))

    def test_banco_indisponivel_mantem_quem_ja_estava_autenticado(self):
        with patch.object(usuarios, "load_user_by_id", side_effect=RuntimeError("timeout")):
            response = self.client.get("/perfil")
        self.assertEqual(response.status_code, 200)

    def test_arquivo_estatico_nao_consulta_o_banco(self):
        carregar = Mock(return_value=USUARIO_ATIVO)
        with patch.object(usuarios, "load_user_by_id", carregar):
            response = self.client.get("/static/css/app.css")
        self.assertEqual(response.status_code, 200)
        response.close()
        carregar.assert_not_called()


class AdminDesenvolvimentoTests(unittest.TestCase):
    def test_sem_hash_o_admin_local_nao_autentica_com_qualquer_senha(self):
        env = {"DEV_BOOTSTRAP_ADMIN_ENABLED": "true", "DEV_BOOTSTRAP_ADMIN_LOGIN": "admin", "DEV_BOOTSTRAP_ADMIN_PASSWORD_HASH": ""}
        with patch.dict(os.environ, env):
            self.assertIsNone(auth.bootstrap_admin_user("admin", "qualquer-coisa"))
            self.assertIsNone(auth.bootstrap_admin_profile())

    def test_admin_local_exige_a_senha_do_hash(self):
        env = {
            "DEV_BOOTSTRAP_ADMIN_ENABLED": "true",
            "DEV_BOOTSTRAP_ADMIN_LOGIN": "admin",
            "DEV_BOOTSTRAP_ADMIN_PASSWORD_HASH": generate_password_hash("senha-certa"),
        }
        with patch.dict(os.environ, env):
            self.assertIsNone(auth.bootstrap_admin_user("admin", "senha-errada"))
            self.assertIsNotNone(auth.bootstrap_admin_user("admin", "senha-certa"))

    def test_admin_local_desabilitado_nunca_autentica(self):
        env = {
            "DEV_BOOTSTRAP_ADMIN_ENABLED": "false",
            "DEV_BOOTSTRAP_ADMIN_PASSWORD_HASH": generate_password_hash("senha-certa"),
        }
        with patch.dict(os.environ, env):
            self.assertIsNone(auth.bootstrap_admin_user("admin", "senha-certa"))


if __name__ == "__main__":
    unittest.main()
