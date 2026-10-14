import logging
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


if __name__ == "__main__":
    unittest.main()
