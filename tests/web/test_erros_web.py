import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app_captacao.app import app
from app_captacao.catalogo import operacoes, relatorios
from app_captacao.core.persistence import usuarios
from app_captacao.web import auditoria

ADMIN_ROW = {"id": 10, "login": "admin", "email": "a@example.com", "area": "ti", "access_id": 1, "ativo": 1, "data_criacao": None}


class ErrosWebTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["user_login"] = "admin"
            session["user_access_id"] = 1
        self._usuario = patch.object(usuarios, "load_user_by_id", return_value=ADMIN_ROW)
        self._usuario.start()
        self.addCleanup(self._usuario.stop)

    def _flashes(self):
        with self.client.session_transaction() as session:
            return [message for _, message in session.get("_flashes", [])]

    def test_id_de_relatorio_invalido_no_formulario_nao_vira_erro_500(self):
        response = self.client.post("/acompanhamento/operacoes/5/relatorios", data={"id_relatorio": "abc"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("Selecione um relatorio.", self._flashes())

    def test_json_de_filtros_nao_expoe_excecao_do_banco(self):
        with patch.object(relatorios, "buscar_relatorio_com_filtros", side_effect=RuntimeError("SELECT Senha FROM dbo.Tabela")):
            response = self.client.get("/relatorios/7/filtros-dados")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("Senha", response.get_json()["error"])

    def test_erro_inesperado_ao_criar_operacao_nao_aparece_na_tela(self):
        with patch.object(operacoes, "criar_operacao", side_effect=RuntimeError("Login failed for user 'sa'")), patch.object(
            auditoria, "log_config"
        ):
            self.client.post("/acompanhamento/operacoes", data={"nome_operacao": "X", "id_relatorio": "1"})
        mensagens = " ".join(self._flashes())
        self.assertIn("Nao foi possivel criar a operacao", mensagens)
        self.assertNotIn("Login failed", mensagens)

    def test_regra_de_negocio_continua_visivel_ao_usuario(self):
        with patch.object(operacoes, "criar_operacao", side_effect=ValueError("Ja existe uma operacao ativa com este nome.")):
            self.client.post("/acompanhamento/operacoes", data={"nome_operacao": "X", "id_relatorio": "1"})
        self.assertIn("Nao foi possivel criar a operacao: Ja existe uma operacao ativa com este nome.", self._flashes())

    def test_falha_ao_gravar_senha_nao_e_anunciada_como_sucesso(self):
        row = {**ADMIN_ROW, "senha": generate_password_hash("atual")}
        with patch.object(usuarios, "load_user_by_login", return_value=row), patch.object(
            usuarios, "atualizar_senha", side_effect=RuntimeError("timeout")
        ):
            self.client.post(
                "/perfil/senha",
                data={"senha_atual": "atual", "nova_senha": "nova-senha", "confirmar_senha": "nova-senha"},
            )
        mensagens = self._flashes()
        self.assertNotIn("Senha atualizada com sucesso.", mensagens)
        self.assertTrue(any("Nao foi possivel atualizar a senha" in m for m in mensagens))


if __name__ == "__main__":
    unittest.main()
