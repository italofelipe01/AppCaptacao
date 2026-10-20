import unittest
from datetime import datetime

from app_captacao.automacao.auditoria_filtros import CampoNaTela, auditar_tela, gerar_markdown


def _campo(id_, rotulo, valor="", obrigatorio=False, name=None, visivel=True):
    return CampoNaTela(id_, id_ if name is None else name, rotulo, "text", valor, visivel, obrigatorio)


def _tela_811(**trocas):
    """Campos da tela do Unidades como foram lidos no Sienge em 2026-10-20."""
    campos = {
        "selecao": _campo("filter.selecao", "Seleção*:", "por Empreendimento", True),
        "grupo": _campo("filter.grupoEmpresa.grupoEmpresaPK.cdGrupoEmpresa", "Grupo de empresa:"),
        "empresa": _campo("filter.empresa.cdEmpresaView", "Empresa*:", obrigatorio=True),
        "nome_empresa": _campo("filter.empresa.nmEmpresa", "Empresa*:", obrigatorio=True),
        "empreendimento": _campo("cdEmpreendView", "Empreendimento*:", obrigatorio=True),
        "posicao": _campo("filter.dtHistorica", "Posição em*:", "20/10/2026", True),
        "ordenacao": _campo("", "Ordenação:", "Tipo de Imóvel", True, name="filter.ordenacao"),
    }
    campos.update(trocas)
    return [campo for campo in campos.values() if campo is not None]


class AuditoriaDaTelaTests(unittest.TestCase):
    def test_tela_igual_a_declaracao_nao_tem_divergencia(self):
        self.assertEqual(auditar_tela("unidades", _tela_811()).divergencias, [])

    def test_campo_declarado_que_sumiu_da_tela(self):
        resultado = auditar_tela("unidades", _tela_811(posicao=None))
        self.assertEqual([(d.tipo, "Posição em" in d.descricao) for d in resultado.divergencias], [("b", True)])

    def test_obrigatorio_da_tela_sem_padrao_e_sem_filtro(self):
        tela = _tela_811(novo=_campo("filter.novo", "Novo campo*:", obrigatorio=True))
        self.assertEqual([d.tipo for d in auditar_tela("unidades", tela).divergencias], ["c"])

    def test_obrigatorio_com_padrao_ou_invisivel_nao_e_cobrado(self):
        tela = _tela_811(
            com_padrao=_campo("filter.a", "Indexador*:", "0", True),
            invisivel=_campo("filter.b", "Escondido*:", obrigatorio=True, visivel=False),
        )
        self.assertEqual(auditar_tela("unidades", tela).divergencias, [])

    def test_obrigatoriedade_ou_padrao_diferente_da_declaracao(self):
        tela = _tela_811(
            empreendimento=_campo("cdEmpreendView", "Empreendimento:"),
            posicao=_campo("filter.dtHistorica", "Posição em*:", "", True),
        )
        self.assertEqual([d.tipo for d in auditar_tela("unidades", tela).divergencias], ["d", "d"])

    def test_filtro_do_cadastro_sem_campo(self):
        cadastro = [
            {"nome": "Empresa", "campo_identificador": "filter.empresa.cdEmpresaView", "acao": ""},
            {"nome": "Período", "campo_identificador": "filter.dtInicioStr", "acao": ""},
            {"nome": "Visualizar", "campo_identificador": "bt", "acao": "click"},
        ]
        divergencias = auditar_tela("unidades", _tela_811(), cadastro).divergencias
        self.assertEqual([(d.tipo, "Período" in d.descricao) for d in divergencias], [("a", True)])

    def test_tela_mui_e_localizada_pelo_rotulo(self):
        tela = [
            _campo("mui-41", "Grupo Empresa"),
            _campo("mui-42", "Empresa"),
            _campo("mui-43", "Empreendimento"),
        ]
        resultado = auditar_tela("quadro_espelho", tela)
        self.assertEqual(resultado.divergencias, [])
        self.assertTrue(all(achado is not None for _, achado in resultado.campos))


class RelatorioDaAuditoriaTests(unittest.TestCase):
    def test_markdown_tem_resumo_e_divergencias(self):
        resultado = auditar_tela("unidades", _tela_811(posicao=None))
        texto = gerar_markdown([resultado], "banco indisponível: OperationalError", datetime(2026, 10, 20, 11, 0))
        self.assertIn("| `unidades` | `/common/page/811` | 5 | 1 |", texto)
        self.assertIn("- (b) 'Posição em' (filter.dtHistorica)", texto)
        self.assertIn("divergência (a) não avaliada", texto)
        self.assertNotIn("las-", texto)


if __name__ == "__main__":
    unittest.main()
