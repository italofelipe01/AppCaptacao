import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_captacao import automacao, consolidacao
from app_captacao.app import app
from app_captacao.core.config import settings
from app_captacao.core.persistence import logs as logs_repo
from app_captacao.execucao import jobs, runner
from tests.consolidacao import planilhas_sienge as sienge

UNIDADES = {"id": 21, "nome": "Unidades", "operacao_nome": "Operacao X"}


def _item(estado, arquivos, relatorio=UNIDADES, mensagem="2 arquivo(s) salvo(s)."):
    return {
        "relatorio_id": relatorio["id"],
        "relatorio_nome": relatorio["nome"],
        "operacao_nome": "Operacao X",
        "estado": estado,
        "mensagem": mensagem,
        "etapa": "" if estado == "baixado" else "download",
        "caminho_final": arquivos[-1] if arquivos else "",
        "arquivos": list(arquivos),
    }


def _resultado(*itens):
    itens = list(itens)
    sucessos = [item for item in itens if item["estado"] == "baixado"]
    return {
        "itens": itens,
        "sucessos": sucessos,
        "falhas": [item for item in itens if item["estado"] != "baixado"],
        "quantidade_baixados": len(sucessos),
        "quantidade_nao_baixados": len(itens) - len(sucessos),
        "resumo": f"{len(sucessos)} relatório(s) baixado(s); {len(itens) - len(sucessos)} não baixado(s).",
    }


class ConsolidacaoNoFimDaExecucaoTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="test")
        jobs._execution_jobs.clear()
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)
        with app.test_request_context("/"):
            self.job_id = jobs.create_execution_job("operacao", [UNIDADES], "Operacao X")

    def tearDown(self):
        self._tmp.cleanup()

    def _unidades(self, *empreendimentos, total_unidades=3):
        return [
            str(sienge.unidades(self.pasta / f"Unidades_242_2026-10-16_{i}.xlsx", e, total_unidades))
            for i, e in enumerate(empreendimentos, start=1)
        ]

    def test_relatorio_baixado_ganha_o_consolidado_como_arquivo_final(self):
        arquivos = self._unidades("1002 - A", "1003 - B")
        resultado = _resultado(_item("baixado", arquivos))
        runner._consolidar_relatorios(self.job_id, resultado, [UNIDADES])

        item = resultado["itens"][0]
        self.assertEqual(item["estado"], "baixado")
        self.assertTrue(Path(item["caminho_final"]).exists())
        self.assertIn("_consolidado_", Path(item["caminho_final"]).name)
        self.assertEqual(item["arquivos"][:2], arquivos)
        self.assertEqual(item["arquivos"][-1], item["caminho_final"])
        self.assertIn("6 linha(s), conferido com os totais do Sienge", item["mensagem"])
        self.assertTrue(resultado["resumo"].endswith("1 consolidado(s)."))

    def test_conferencia_que_falha_nao_muda_o_estado_nem_o_arquivo_final(self):
        arquivos = self._unidades("1002 - A", total_unidades=99)
        resultado = _resultado(_item("baixado", arquivos))
        runner._consolidar_relatorios(self.job_id, resultado, [UNIDADES])

        item = resultado["itens"][0]
        self.assertEqual((item["estado"], item["caminho_final"], item["arquivos"]), ("baixado", arquivos[-1], arquivos))
        self.assertIn("Consolidado não gerado: Unidades_242_2026-10-16_1.xlsx: Quantidade de unidades", item["mensagem"])
        self.assertIn("0 consolidado(s), 1 não gerado(s)", resultado["resumo"])
        self.assertEqual(list(self.pasta.glob("*consolidado*")), [])

    def test_relatorio_que_falhou_no_meio_nao_e_consolidado(self):
        arquivos = self._unidades("1002 - A")
        resultado = _resultado(_item("nao_baixado", arquivos, mensagem="Falhou na 2a empresa."))
        runner._consolidar_relatorios(self.job_id, resultado, [UNIDADES])

        self.assertEqual(resultado["itens"][0]["mensagem"], "Falhou na 2a empresa.")
        self.assertEqual(list(self.pasta.glob("*consolidado*")), [])
        self.assertNotIn("consolidado", resultado["resumo"])

    def test_relatorio_sem_layout_conhecido_fica_como_estava(self):
        conciliado = {"id": 6, "nome": "Extrato conciliado"}
        arquivo = self.pasta / "Extrato conciliado_1_2026-10-16.xlsx"
        arquivo.write_bytes(b"x")
        resultado = _resultado(_item("baixado", [str(arquivo)], relatorio=conciliado))
        resumo_antes = resultado["resumo"]
        runner._consolidar_relatorios(self.job_id, resultado, [conciliado])
        self.assertEqual(resultado["resumo"], resumo_antes)
        self.assertEqual(resultado["itens"][0]["caminho_final"], str(arquivo))

    def test_erro_inesperado_na_consolidacao_mantem_o_relatorio_baixado(self):
        arquivos = self._unidades("1002 - A")
        resultado = _resultado(_item("baixado", arquivos))
        with patch.object(consolidacao, "consolidar", side_effect=MemoryError("planilha enorme")):
            runner._consolidar_relatorios(self.job_id, resultado, [UNIDADES])
        item = resultado["itens"][0]
        self.assertEqual(item["estado"], "baixado")
        self.assertIn("Consolidado não gerado: erro inesperado", item["mensagem"])

    def test_flag_desligada_nao_consolida(self):
        arquivos = self._unidades("1002 - A")
        resultado = _resultado(_item("baixado", arquivos))
        with patch.object(settings, "CONSOLIDAR_RELATORIOS", False):
            runner._consolidar_relatorios(self.job_id, resultado, [UNIDADES])
        self.assertEqual(resultado["itens"][0]["caminho_final"], arquivos[-1])
        self.assertEqual(list(self.pasta.glob("*consolidado*")), [])

    def test_job_concluido_mostra_o_consolidado_na_tela(self):
        arquivos = self._unidades("1002 - A", "1003 - B")

        def operacao(_email, _senha, _relatorios, on_report_event):
            on_report_event("sucesso", UNIDADES, {"caminho_final": arquivos[-1], "arquivos": arquivos})
            return _resultado(_item("baixado", arquivos))

        with patch.object(automacao, "executar_relatorios_em_sequencia", side_effect=operacao), patch.object(
            logs_repo, "registrar_log_operacao"
        ):
            runner.run_execution_job(self.job_id, "operacao", "user", "x", [UNIDADES], {"login": "ana"}, "Operacao X")

        job = jobs.get_execution_job(self.job_id)
        assert job is not None
        self.assertEqual(job["estado"], "concluida")
        self.assertIn("_consolidado_", job["itens"][0]["caminho_final"])
        self.assertIn("1 consolidado(s)", job["resumo"])


if __name__ == "__main__":
    unittest.main()
