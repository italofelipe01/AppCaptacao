import unittest

from app_captacao.catalogo import regras


class ResolucaoDoExecutorTests(unittest.TestCase):
    def test_url_tem_prioridade_sobre_id_e_nome(self):
        executor = regras.obter_executor_relatorio("Vendas", 3, "https://ebm.sienge.com.br/sienge/8/index.html#/common/page/723")
        self.assertEqual(executor, "preco_total_vendas")

    def test_trecho_de_url_precisa_terminar_a_rota(self):
        self.assertEqual(regras.obter_executor_relatorio("", url_relatorio="https://x/#/common/page/7230"), "")
        self.assertEqual(regras.obter_executor_relatorio("", url_relatorio="https://x/#/common/page/723?aba=1"), "preco_total_vendas")
        self.assertEqual(regras.obter_executor_relatorio("", url_relatorio="https://x/#/common/page/723/"), "preco_total_vendas")

    def test_id_do_relatorio_resolve_sem_url(self):
        self.assertEqual(regras.obter_executor_relatorio("Qualquer nome", 7), "extrato_cliente_historico")

    def test_id_da_linha_de_vinculo_nao_decide_o_executor(self):
        # O vinculo 7 de uma operacao e so a 7a linha criada: o relatorio continua sendo Vendas.
        relatorio = {"id_relatorio": 3, "id_relatorio_operacao": 7, "nome": "Vendas", "url": "https://x/#/common/page/708"}
        self.assertEqual(regras.executor_do_relatorio(relatorio), "vendas")

    def test_nome_com_acento_resolve_como_sem_acento(self):
        self.assertEqual(regras.obter_executor_relatorio("Títulos Distratados"), "titulos_distratados")
        self.assertEqual(regras.obter_executor_relatorio("RELATÓRIO ANALÍTICO DE APROPRIAÇÕES"), "analitico_propriedade")

    def test_nome_com_texto_a_mais_usa_a_chave_mais_especifica(self):
        self.assertEqual(regras.obter_executor_relatorio("Relatório de Preço Total de Vendas - EBM"), "preco_total_vendas")
        self.assertEqual(regras.obter_executor_relatorio("Mapa de Venda (mensal)"), "mapa_venda")

    def test_nome_desconhecido_nao_tem_executor(self):
        self.assertEqual(regras.obter_executor_relatorio("Relatorio novo sem cadastro"), "")


class FiltrosTests(unittest.TestCase):
    def test_filtro_obrigatorio_vazio_e_cobrado(self):
        relatorio = {"nome": "Vendas", "filtros": [{"id": 1, "nome": "Empresa", "campo_identificador": "cdEmpresaView", "acao": "", "valor": ""}]}
        self.assertEqual(regras.filtros_obrigatorios_sem_valor(relatorio), ["Empresa"])

    def test_filtro_opcional_do_executor_nao_e_cobrado(self):
        relatorio = {
            "nome": "Titulos Quitados",
            "filtros": [{"id": 2, "nome": "Centro de custo", "campo_identificador": "centroCusto.cdEmpreendView", "acao": "", "valor": ""}],
        }
        self.assertEqual(regras.filtros_obrigatorios_sem_valor(relatorio), [])

    def test_acao_de_clique_nao_exige_valor(self):
        relatorio = {"nome": "Vendas", "filtros": [{"id": 3, "nome": "Gerar", "campo_identificador": "btn", "acao": "click", "valor": ""}]}
        self.assertEqual(regras.filtros_obrigatorios_sem_valor(relatorio), [])

    def test_filtro_fixo_so_vale_para_o_executor_de_unidades(self):
        selecao = {"id": 9, "nome": "Selecao", "campo_identificador": "filter.selecao", "acao": "", "valor": ""}
        unidades = regras.aplicar_filtros_fixos({"nome": "Relatório de Unidades", "filtros": [dict(selecao)]})
        vendas = regras.aplicar_filtros_fixos({"nome": "Vendas", "id": 3, "filtros": [dict(selecao)]})

        fixo = unidades["filtros"][0]
        self.assertEqual((fixo["valor"], fixo["automatico"], fixo["tipo_campo_valor"]), ("por Empreendimento", True, "CLICK"))
        self.assertNotIn("automatico", vendas["filtros"][0])
        self.assertEqual(regras.filtros_obrigatorios_sem_valor(unidades), [])


if __name__ == "__main__":
    unittest.main()
