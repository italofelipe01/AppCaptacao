import unittest
from unittest.mock import patch

from app_captacao.app import app
from app_captacao.execucao import jobs


class JobsMemoriaTests(unittest.TestCase):
    def setUp(self):
        jobs._execution_jobs.clear()

    def tearDown(self):
        jobs._execution_jobs.clear()

    def test_jobs_concluidos_antigos_sao_descartados_e_o_em_andamento_fica(self):
        with patch.object(jobs, "MAX_JOBS_CONCLUIDOS", 3), app.test_request_context("/"):
            concluidos = []
            for _ in range(6):
                job_id = jobs.create_execution_job("relatorio", [{"id": 1, "nome": "A"}])
                jobs.finish_execution_job(job_id, {"itens": [], "resumo": "ok"})
                concluidos.append(job_id)
            em_andamento = jobs.create_execution_job("relatorio", [{"id": 1, "nome": "A"}])

        self.assertIn(em_andamento, jobs._execution_jobs)
        self.assertEqual([j for j in concluidos if j in jobs._execution_jobs], concluidos[-3:])


class UmaAutomacaoPorVezTests(unittest.TestCase):
    def setUp(self):
        jobs._execution_jobs.clear()

    def tearDown(self):
        jobs._execution_jobs.clear()

    def test_outra_sessao_nao_inicia_enquanto_uma_automacao_roda(self):
        # Sessoes diferentes, mesmo computador: o Edge e a pasta de downloads sao compartilhados.
        with app.test_request_context("/"):
            jobs.create_execution_job("relatorio", [{"id": 1, "nome": "A"}])
        with app.test_request_context("/"), self.assertRaises(jobs.ExecucaoEmAndamentoError):
            jobs.create_execution_job("relatorio", [{"id": 2, "nome": "B"}])

    def test_nova_execucao_liberada_quando_a_anterior_termina(self):
        with app.test_request_context("/"):
            primeiro = jobs.create_execution_job("relatorio", [{"id": 1, "nome": "A"}])
            jobs.finish_execution_job(primeiro, {"itens": [], "resumo": "ok"})
            segundo = jobs.create_execution_job("relatorio", [{"id": 1, "nome": "A"}])
        self.assertNotEqual(primeiro, segundo)


if __name__ == "__main__":
    unittest.main()
