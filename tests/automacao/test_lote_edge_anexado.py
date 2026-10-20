"""Operacao em lote no Edge anexado, como no teste real que falhou em 2026-10-15.

O Edge expunha o dialogo interno edge://sync-confirmation-dialog/ como janela. Cada
executor tentava fecha-lo, perdia 20 s, falhava, deixava o driver nesse dialogo e o
relatorio seguinte fechava a aba do Sienge: a sessao do Selenium morria e os 7
relatorios terminavam sem arquivo.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_captacao.automacao import downloads, execucao, login, navegador
from app_captacao.automacao import relatorios as relatorios_dedicados
from tests.automacao.test_navegador_janelas import DIALOGO, SIENGE, _EdgeAnexado

RELATORIOS_DO_TESTE = [
    (17, "Analítico de Apropriações", "#/common/page/473"),
    (18, "Extrato Cliente Historico", "#/common/page/3012"),
    (22, "Mapa de Vendas", "#/common/page/5084"),
    (14, "Relatório de Preço Total de Vendas", "#/common/page/723"),
    (13, "Relatório de Títulos Distratados", "#/common/page/4140"),
    (3, "Relatório de Vendas", "#/common/page/708"),
    (21, "Unidades", "#/common/page/999"),
]


class _EdgeDaOperacao(_EdgeAnexado):
    def __init__(self):
        super().__init__()
        del self.janelas["C3" * 16]  # sem popup aberto antes do primeiro relatorio
        self.popups = 0

    def get(self, url):
        self.janelas[self.atual] = url

    def refresh(self):
        # O Sienge reabre a ultima tela visitada: o primeiro relatorio pode ja estar na URL atual.
        self.recarregamentos = getattr(self, "recarregamentos", 0) + 1

    def execute_script(self, _script, *args):
        return "complete"

    def abrir_popup(self):
        self.popups += 1
        handle = f"P{self.popups:031d}"
        self.janelas[handle] = "https://ebm.sienge.com.br/sienge/relatorio.do"


class LoteNoEdgeAnexadoTests(unittest.TestCase):
    def test_sete_relatorios_com_varias_empresas_terminam_baixados(self):
        driver = _EdgeDaOperacao()
        relatorios = [
            {"id": id_, "nome": nome, "url": f"https://ebm.sienge.com.br/sienge/8/index.html{rota}", "filtros": []}
            for id_, nome, rota in RELATORIOS_DO_TESTE
        ]

        with tempfile.TemporaryDirectory() as pasta:

            def executor_com_popup(_executor, driver_atual, _wait, relatorio_config, _contexto):
                for empresa in ("242", "243"):
                    driver_atual.abrir_popup()  # "Visualizar" abre a janela do relatorio
                    navegador.fechar_janelas_extras(driver_atual)
                    arquivo = Path(pasta) / f"{relatorio_config['id']}_{empresa}.xlsx"
                    arquivo.write_bytes(b"planilha")
                    downloads.copiar_download_para_sharepoint(relatorio_config, arquivo)

            with patch.object(navegador, "criar_driver", return_value=driver), patch.object(login, "fazer_login"), patch.object(
                relatorios_dedicados, "executar_relatorio_dedicado", side_effect=executor_com_popup
            ), patch.object(downloads, "aguardar_pasta_download_estabilizar", return_value=True), patch.object(
                downloads, "DOWNLOAD_DIR", pasta
            ), patch.object(execucao.time, "sleep"):
                resultado = execucao.executar_relatorios_em_sequencia("ana@ebm.com.br", "x", relatorios)

        self.assertEqual(resultado["quantidade_baixados"], 7, [item["mensagem"] for item in resultado["falhas"]])
        self.assertTrue(all(len(item["arquivos"]) == 2 for item in resultado["itens"]))
        self.assertIn(SIENGE, driver.janelas)
        self.assertIn(DIALOGO, driver.janelas)  # o dialogo interno nunca e fechado
        self.assertEqual(len(driver.fechadas), 14)  # so os popups dos relatorios
        self.assertIn("Arquivos em:", resultado["resumo"])


if __name__ == "__main__":
    unittest.main()
