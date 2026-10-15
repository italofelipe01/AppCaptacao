import unittest

from app_captacao.automacao.relatorios.executores import extrato_cliente_historico


class ExtratoClienteHistoricoTests(unittest.TestCase):
    def test_empreendimento_unico_vale_para_todas_as_empresas(self):
        self.assertEqual(extrato_cliente_historico._calcular_pares_empresa_empreendimento(["1", "2", "3"], ["10"]), 3)

    def test_listas_de_tamanhos_diferentes_sao_erro_e_nao_perdem_empresa(self):
        with self.assertRaises(ValueError):
            extrato_cliente_historico._calcular_pares_empresa_empreendimento(["1", "2", "3"], ["10", "20"])

    def test_sem_empreendimento_o_erro_e_claro(self):
        with self.assertRaisesRegex(ValueError, "empresa e empreendimento"):
            extrato_cliente_historico._calcular_pares_empresa_empreendimento(["1"], [])


if __name__ == "__main__":
    unittest.main()
