import unittest
from unittest.mock import patch

from app_captacao.app import app
from app_captacao.catalogo import relatorios
from app_captacao.core.config import settings
from app_captacao.core.persistence import usuarios
from app_captacao.execucao import jobs

USUARIO = {"id": 30, "login": "execucao", "email": "", "area": "", "access_id": 3, "ativo": 1, "data_criacao": None}
PAYLOAD = {"id": 3, "nome": "Vendas", "url": "https://x/#/common/page/708", "filtros": []}


class ProcessarTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = USUARIO["id"]
            session["user_login"] = USUARIO["login"]
            session["user_access_id"] = USUARIO["access_id"]
        usuario = patch.object(usuarios, "load_user_by_id", return_value=USUARIO)
        usuario.start()
        self.addCleanup(usuario.stop)

    def _flashes(self):
        with self.client.session_transaction() as session:
            return [message for _, message in session.get("_flashes", [])]

    def _processar(self, **dados):
        formulario = {"email": "ana@empresa.com", "senha": "x", "modo": "completo", "relatorio": "3", **dados}
        with patch.object(relatorios, "montar_payload_execucao", return_value=dict(PAYLOAD)), patch.object(
            jobs, "create_execution_job"
        ) as criar, patch("app_captacao.web.routes_execucao.threading.Thread"):
            self.client.post("/processar", data=formulario)
        return criar

    def test_link_web_do_sharepoint_e_recusado_antes_de_abrir_o_navegador(self):
        criar = self._processar(sharepoint_link="https://empresa.sharepoint.com/sites/cap")
        criar.assert_not_called()
        self.assertTrue(any("Link do SharePoint" in mensagem for mensagem in self._flashes()))

    def test_destino_relativo_e_recusado(self):
        criar = self._processar(sharepoint_link="Relatorios")
        criar.assert_not_called()
        self.assertTrue(any("caminho completo" in mensagem for mensagem in self._flashes()))

    def test_destino_valido_inicia_a_execucao(self):
        criar = self._processar(sharepoint_link=r"\\servidor\captacao")
        criar.assert_called_once()

    def test_filtro_sem_campo_no_sienge_e_recusado_quando_a_recusa_esta_ligada(self):
        payload = {
            "id": 21,
            "nome": "Unidades",
            "url": "https://x/#/common/page/811",
            "filtros": [{"id": 5, "nome": "Data inicial", "campo_identificador": "filter.dtInicioStr", "acao": "", "valor": "2026-09-01"}],
        }
        formulario = {"email": "a@b.com", "senha": "x", "modo": "completo", "relatorio": "21"}
        for recusar, deve_iniciar in ((True, False), (False, True)):
            with self.subTest(recusar=recusar), patch.object(settings, "RECUSAR_FILTROS_SEM_CAMPO", recusar), patch.object(
                relatorios, "montar_payload_execucao", return_value=dict(payload)
            ), patch.object(jobs, "create_execution_job") as criar, patch("app_captacao.web.routes_execucao.threading.Thread"):
                self.client.post("/processar", data=formulario)
            self.assertEqual(criar.called, deve_iniciar)
        self.assertTrue(any("sem campo correspondente na tela do Sienge: Data inicial" in m for m in self._flashes()))

    def test_automacao_de_outra_sessao_rodando_e_avisada_sem_virar_erro(self):
        with patch.object(relatorios, "montar_payload_execucao", return_value=dict(PAYLOAD)), patch.object(
            jobs, "create_execution_job", side_effect=jobs.ExecucaoEmAndamentoError("Ja existe uma execucao em andamento neste computador.")
        ), patch("app_captacao.web.routes_execucao.threading.Thread") as thread:
            self.client.post("/processar", data={"email": "a@b.com", "senha": "x", "modo": "completo", "relatorio": "3"})
        thread.assert_not_called()
        self.assertIn("Ja existe uma execucao em andamento neste computador.", self._flashes())


if __name__ == "__main__":
    unittest.main()
