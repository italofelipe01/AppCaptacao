import unittest
from unittest.mock import patch

from app_captacao.app import app
from app_captacao.core.persistence import logs as logs_repo
from app_captacao.core.persistence import usuarios

USUARIO_CADASTRO = {"id": 20, "login": "operador", "email": "", "area": "", "access_id": 2, "ativo": 1, "data_criacao": None}
USUARIO_ADMIN = {**USUARIO_CADASTRO, "id": 10, "login": "admin", "access_id": 1}
LOG_ADMINISTRATIVO = [{"usuario": "admin", "evento": "usuario_criacao", "detalhe": "Usuario criado.", "data_evento": "-", "payload_json": "{}"}]


class ExportacaoDeLogsTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app.test_client()

    def _entrar_como(self, usuario):
        with self.client.session_transaction() as session:
            session["user_id"] = usuario["id"]
            session["user_login"] = usuario["login"]
            session["user_access_id"] = usuario["access_id"]

    def _exportar(self, usuario):
        self._entrar_como(usuario)
        with patch.object(usuarios, "load_user_by_id", return_value=usuario), patch.object(
            logs_repo, "load_logs_configuracao", return_value=LOG_ADMINISTRATIVO
        ) as carregar_adm, patch.object(logs_repo, "load_logs_operacao", return_value=[]):
            resposta = self.client.get("/logs/exportar?aba=adm")
        return resposta, resposta.get_json(silent=True) or {}, carregar_adm

    def test_cadastro_de_operacao_nao_exporta_a_aba_administrativa(self):
        resposta, dados, carregar_adm = self._exportar(USUARIO_CADASTRO)
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(dados["aba"], "operacao")
        self.assertEqual(dados["registros"], [])
        carregar_adm.assert_not_called()

    def test_administrador_exporta_a_aba_administrativa(self):
        _, dados, carregar_adm = self._exportar(USUARIO_ADMIN)
        self.assertEqual(dados["aba"], "adm")
        self.assertEqual(dados["registros"], LOG_ADMINISTRATIVO)
        carregar_adm.assert_called_once()

    def test_perfil_de_execucao_nao_exporta_logs(self):
        execucao = {**USUARIO_CADASTRO, "access_id": 3}
        resposta, _, carregar_adm = self._exportar(execucao)
        self.assertEqual(resposta.status_code, 302)
        carregar_adm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
