import io
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_captacao.core.shared import log_tecnico


class LogTecnicoTests(unittest.TestCase):
    def tearDown(self):
        log_tecnico.desligar_log_tecnico()

    def test_mensagens_da_automacao_vao_para_o_arquivo_sem_duplicar_handlers(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(log_tecnico, "pasta_de_logs", return_value=Path(tmp)):
            arquivo = log_tecnico.configurar_log_tecnico(console=False)
            log_tecnico.configurar_log_tecnico(console=False)
            logging.getLogger("app_captacao.automacao.execucao").info("Executando relatorio 1/2")
            logging.getLogger("terceiros").info("nao deve aparecer")
            log_tecnico.desligar_log_tecnico()

            conteudo = arquivo.read_text(encoding="utf-8")
        self.assertEqual(conteudo.count("Executando relatorio 1/2"), 1)
        self.assertNotIn("nao deve aparecer", conteudo)

    def test_console_mostra_as_etapas_e_os_erros_com_os_marcadores_do_checklist(self):
        console = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            log_tecnico, "pasta_de_logs", return_value=Path(tmp)
        ), patch.object(sys, "stderr", console):
            log_tecnico.configurar_log_tecnico(console=True)
            logging.getLogger("app_captacao.automacao.login").info("Login Sienge: tela sienge_entrar.")
            logging.getLogger("app_captacao.automacao.login").warning("Usuario ja conectado.")
            logging.getLogger("app_captacao.automacao.execucao").error("Relatorio nao baixado.")
            logging.getLogger("terceiros").info("nao deve aparecer")
            log_tecnico.desligar_log_tecnico()

        linhas = console.getvalue().splitlines()
        self.assertRegex(linhas[0], r"^\d\d:\d\d:\d\d \[INFO \] Login Sienge: tela sienge_entrar\.$")
        self.assertRegex(linhas[1], r"\[AVISO\] Usuario ja conectado\.$")
        self.assertRegex(linhas[2], r"\[ERRO \] Relatorio nao baixado\.$")
        self.assertEqual(len(linhas), 3)


if __name__ == "__main__":
    unittest.main()
