import unittest

from app_captacao.catalogo import parametros
from app_captacao.catalogo.parametros import LinhaParametro, linhas_de_parametros


def _filtro(nome, campo, valor="", **extras):
    return {"id": nome, "nome": nome, "campo_identificador": campo, "acao": "", "valor": valor, **extras}


class LinhasDeParametrosTests(unittest.TestCase):
    def test_unidades_mostra_cada_filtro_com_o_campo_do_sienge(self):
        relatorio = {
            "nome": "Unidades",
            "filtros": [
                _filtro("Seleção", "filter.selecao", "por Empreendimento", automatico=True, tipo_campo_valor="CLICK"),
                _filtro("Grupo de empresa", "filter.grupoEmpresa.grupoEmpresaPK.cdGrupoEmpresa", "18,15"),
                _filtro("Empresa", "filter.empresa.cdEmpresaView", "242,101,92"),
                _filtro("Empreendimento", "cdEmpreendView", "1002, 1003,1330"),
                _filtro("Posição em", "dtPosicao", "2026-09-30", tipo_campo_valor="DATE"),
            ],
        }
        self.assertEqual(
            linhas_de_parametros(relatorio),
            [
                LinhaParametro("Seleção", "Seleção", "por Empreendimento", parametros.PREENCHIDO_AUTOMATICAMENTE),
                LinhaParametro("Grupo de empresa", "Grupo de empresa", "18, 15"),
                LinhaParametro("Empresa", "Empresa", "242, 101, 92"),
                LinhaParametro("Empreendimento", "Empreendimento", "1002, 1003, 1330"),
                LinhaParametro("Posição em", "Posição em", "30/09/2026"),
            ],
        )

    def test_data_do_campo_sai_em_dia_mes_ano_mesmo_sem_tipo_date(self):
        linha = linhas_de_parametros({"nome": "Unidades", "filtros": [_filtro("Data", "filter.dtHistorica", "2026-08-31")]})[0]
        self.assertEqual(linha.valor, "31/08/2026")

    def test_vazio_diz_que_o_sienge_usa_o_padrao_da_tela(self):
        linha = linhas_de_parametros({"nome": "Unidades", "filtros": [_filtro("Posição em", "filter.dtHistorica")]})[0]
        self.assertEqual(linha.valor, parametros.SEM_VALOR)
        self.assertEqual(linha.observacao, f"{parametros.NAO_INFORMADO} (data do dia)")

    def test_filtro_sem_campo_no_sienge_fica_marcado(self):
        linha = linhas_de_parametros({"nome": "Unidades", "filtros": [_filtro("Período", "filter.dtInicioStr", "2026-09-01")]})[0]
        self.assertEqual(linha.campo_no_sienge, parametros.SEM_VALOR)
        self.assertEqual(linha.observacao, parametros.SEM_CAMPO_NO_SIENGE)

    def test_valor_do_cadastro_diferente_do_fixo_nao_e_o_usado(self):
        relatorio = {"nome": "Vendas", "id": 3, "filtros": [_filtro("Tipo", "filter.tpRelatorio", "Simplificado")]}
        linha = linhas_de_parametros(relatorio)[0]
        self.assertEqual(linha.valor, "Consolidado")
        self.assertIn("'Simplificado'", linha.observacao)

    def test_acao_de_clique_aparece_como_acao_automatica(self):
        linha = linhas_de_parametros({"nome": "Vendas", "id": 3, "filtros": [_filtro("Gerar", "btn", acao="click")]})[0]
        self.assertEqual((linha.valor, linha.observacao), (parametros.SEM_VALOR, parametros.ACAO_AUTOMATICA))

    def test_relatorio_sem_filtros_tem_uma_linha_de_aviso(self):
        self.assertEqual(linhas_de_parametros({"nome": "Unidades", "filtros": []})[0].filtro, parametros.NENHUM_FILTRO)
        self.assertEqual(linhas_de_parametros(None)[0].filtro, parametros.NENHUM_FILTRO)


if __name__ == "__main__":
    unittest.main()
