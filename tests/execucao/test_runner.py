import unittest
from unittest.mock import patch

from app_captacao import automacao
from app_captacao.app import app
from app_captacao.core.persistence import logs as logs_repo
from app_captacao.execucao import jobs, runner


class BackgroundExecutionTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="test")
        jobs._execution_jobs.clear()

    def test_job_tracks_each_report_until_partial_result(self):
        reports = [
            {"id": 1, "nome": "Relatorio A", "operacao_nome": "Operacao X"},
            {"id": 2, "nome": "Relatorio B", "operacao_nome": "Operacao X"},
        ]
        with app.test_request_context("/"):
            job_id = jobs.create_execution_job("operacao", reports, "Operacao X")

        result = {
            "itens": [
                {
                    "relatorio_id": 1,
                    "relatorio_nome": "Relatorio A",
                    "operacao_nome": "Operacao X",
                    "estado": "baixado",
                    "mensagem": "",
                    "etapa": "",
                    "caminho_final": r"C:\Destino\a.xlsx",
                    "arquivos": [r"C:\Destino\a.xlsx"],
                },
                {
                    "relatorio_id": 2,
                    "relatorio_nome": "Relatorio B",
                    "operacao_nome": "Operacao X",
                    "estado": "nao_baixado",
                    "mensagem": "Falha ao copiar",
                    "etapa": "copia",
                    "caminho_final": "",
                    "arquivos": [],
                },
            ],
            "sucessos": [{}],
            "falhas": [{}],
            "quantidade_baixados": 1,
            "quantidade_nao_baixados": 1,
            "resumo": "1 relatorio baixado; 1 nao baixado.",
        }

        def fake_sequence(_email, _senha, _reports, on_report_event):
            on_report_event("processando", reports[0], {})
            on_report_event(
                "sucesso",
                reports[0],
                {"caminho_final": r"C:\Destino\a.xlsx", "arquivos": [r"C:\Destino\a.xlsx"]},
            )
            on_report_event("processando", reports[1], {})
            on_report_event("erro", reports[1], {"mensagem": "Falha ao copiar", "etapa": "copia"})
            return result

        with patch.object(automacao, "executar_relatorios_em_sequencia", side_effect=fake_sequence), patch.object(
            logs_repo, "registrar_log_operacao"
        ) as registrar:
            runner.run_execution_job(
                job_id,
                "operacao",
                "user",
                "password",
                reports,
                {"login": "tester"},
                "Operacao X",
            )

        job = jobs._execution_jobs[job_id]
        self.assertEqual(job["estado"], "concluida")
        self.assertEqual(job["quantidade_baixados"], 1)
        self.assertEqual(job["quantidade_nao_baixados"], 1)
        self.assertEqual([item["estado"] for item in job["itens"]], ["baixado", "nao_baixado"])
        self.assertEqual(registrar.call_args.args[0], "tester")

    def test_falha_inesperada_preserva_o_que_ja_foi_baixado(self):
        reports = [{"id": 1, "nome": "A"}, {"id": 2, "nome": "B"}, {"id": 3, "nome": "C"}]
        with app.test_request_context("/"):
            job_id = jobs.create_execution_job("operacao", reports, "Operacao X")

        def quebra_no_segundo(_email, _senha, _reports, on_report_event):
            on_report_event("sucesso", reports[0], {"caminho_final": r"C:\Destino\a.xlsx", "arquivos": [r"C:\Destino\a.xlsx"]})
            on_report_event("processando", reports[1], {})
            raise RuntimeError("invalid session id: chrome not reachable")

        with patch.object(automacao, "executar_relatorios_em_sequencia", side_effect=quebra_no_segundo), patch.object(
            logs_repo, "registrar_log_operacao"
        ) as registrar:
            runner.run_execution_job(job_id, "operacao", "user", "password", reports, {"login": "tester"}, "Operacao X")

        job = jobs._execution_jobs[job_id]
        estados = [(item["estado"], item["etapa"]) for item in job["itens"]]
        self.assertEqual(estados, [("baixado", ""), ("nao_baixado", "execucao"), ("ignorado", "execucao")])
        self.assertEqual(job["itens"][0]["caminho_final"], r"C:\Destino\a.xlsx")
        self.assertEqual((job["quantidade_baixados"], job["quantidade_nao_baixados"]), (1, 2))
        self.assertNotIn("chrome not reachable", " ".join(item["mensagem"] for item in job["itens"]))
        self.assertEqual(registrar.call_args.args[1], "erro")


if __name__ == "__main__":
    unittest.main()
