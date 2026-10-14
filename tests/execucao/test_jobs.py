import unittest
from unittest.mock import patch

from app_captacao.app import app
from app_captacao.execucao import jobs


class JobsMemoriaTests(unittest.TestCase):
    def setUp(self):
        jobs._execution_jobs.clear()

    def tearDown(self):
        jobs._execution_jobs.clear()

    def test_jobs_concluidos_antigos_sao_descartados_e_os_em_andamento_ficam(self):
        with patch.object(jobs, "MAX_JOBS_CONCLUIDOS", 3), app.test_request_context("/"):
            em_andamento = jobs.create_execution_job("relatorio", [{"id": 1, "nome": "A"}])
            concluidos = []
            for _ in range(6):
                job_id = jobs.create_execution_job("relatorio", [{"id": 1, "nome": "A"}])
                jobs.finish_execution_job(job_id, {"itens": [], "resumo": "ok"})
                concluidos.append(job_id)
            jobs.create_execution_job("relatorio", [{"id": 1, "nome": "A"}])

        self.assertIn(em_andamento, jobs._execution_jobs)
        self.assertEqual([j for j in concluidos if j in jobs._execution_jobs], concluidos[-3:])


if __name__ == "__main__":
    unittest.main()
