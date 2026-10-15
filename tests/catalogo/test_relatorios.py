import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app_captacao.catalogo import relatorios


def _linha(id_filtro, campo, nome="Filtro"):
    return SimpleNamespace(
        IdCapRecursoRelatorio=5,
        NomeRelatorio="Unidades",
        UrlRelatorio="https://x/#/common/page/999",
        IdFiltro=id_filtro,
        NomeFiltro=nome,
        TipoCampo="ID",
        TipoCampoValor="",
        IframeIndex=0,
        CampoIdentificador=campo,
        Acao="",
    )


class _Cursor:
    def __init__(self, linhas):
        self._linhas = linhas
        self.consultas = []

    def execute(self, query, params=()):
        self.consultas.append(" ".join(query.split()))

    def fetchall(self):
        return self._linhas


class _Conexao:
    def __init__(self, linhas):
        self.cursor_ = _Cursor(linhas)

    def cursor(self):
        return self.cursor_

    def close(self):
        pass


class CatalogoDeRelatoriosTests(unittest.TestCase):
    def test_filtro_inativo_fica_no_join_e_nao_esconde_o_relatorio(self):
        consulta = " ".join(relatorios.RELATORIO_COM_FILTROS_QUERY.split())
        juncao, filtro_where = consulta.split(" WHERE ", 1)
        self.assertIn("AND f.IdAtivo = 1", juncao)
        self.assertNotIn("f.IdAtivo", filtro_where)

    def test_relatorio_sem_filtros_ativos_volta_com_lista_vazia(self):
        sem_filtro = _linha(None, None)
        with patch.object(relatorios, "get_db_connection", return_value=_Conexao([sem_filtro])):
            relatorio = relatorios.buscar_relatorio_com_filtros(5)
        assert relatorio is not None
        self.assertEqual(relatorio["nome"], "Unidades")
        self.assertEqual(relatorio["filtros"], [])

    def test_payload_usa_valor_da_tela_e_mantem_o_filtro_fixo(self):
        linhas = [_linha(1, "filter.selecao", "Selecao"), _linha(2, "cdEmpresaView", "Empresa")]
        with patch.object(relatorios, "get_db_connection", return_value=_Conexao(linhas)):
            payload = relatorios.montar_payload_execucao(5, {"filtro_1": "digitado", "filtro_2": "12"})
        assert payload is not None
        valores = {filtro["id"]: filtro["valor"] for filtro in payload["filtros"]}
        self.assertEqual(valores, {1: "por Empreendimento", 2: "12"})


if __name__ == "__main__":
    unittest.main()
