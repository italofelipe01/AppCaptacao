import unittest
from unittest.mock import Mock, patch

from app_captacao.automacao import campos
from app_captacao.automacao.relatorios.executores import unidades


class PosicaoEmTests(unittest.TestCase):
    """"Posição em" (filter.dtHistorica) chegava no payload e era descartado: o Sienge gerava com a data do dia.

    Execucao real de 2026-10-16: os 5 arquivos sairam com "Posição em 16/10/2026".
    """

    def setUp(self):
        # Tela do Sienge: id do campo -> valor. "Posição em" abre com a data do dia.
        self.tela = {unidades.POSICAO_EM_CAMPO: "20/10/2026"}
        self.eventos = []
        self.contexto = {
            "logger": Mock(),
            "normalizar_valor": campos.normalizar_valor_automacao,
            "default_report_wait": 5,
            "marcar_inicio_download": lambda: None,
            "renomear_download": lambda _config, empresa, _inicio: self.eventos.append(f"arquivo {empresa}"),
        }

    def _relatorio(self, posicao_em):
        filtros = [
            {"nome": "Empresa", "campo_identificador": "filter.empresa.cdEmpresaView", "valor": "242"},
            {"nome": "Empreendimento", "campo_identificador": "cdEmpreendView", "valor": "1002,1003"},
        ]
        if posicao_em:
            filtros.append(posicao_em)
        return {"nome": "Unidades", "filtros": filtros}

    def _executar(self, relatorio, tela_aceita_data=True, selecionar=None):
        eventos, tela = self.eventos, self.tela

        def preencher(_driver, _wait, identificadores, valor, _logger):
            campo = identificadores[0]
            if campo != unidades.POSICAO_EM_CAMPO or tela_aceita_data:
                tela[campo] = valor
            eventos.append(f"{campo}={valor}")

        def localizar(_driver, _wait, identificador):
            return Mock(get_attribute=lambda _atributo: tela.get(identificador, ""))

        class _Acoes:
            def __init__(self, _driver):
                pass

            def send_keys(self, *_teclas):
                return self

            def perform(self):
                eventos.append("enter")

        with patch.object(unidades, "_preencher_campo", preencher), patch.object(
            unidades, "_localizar_no_primeiro_iframe", localizar
        ), patch.object(unidades, "_selecionar_select", selecionar or Mock()), patch.object(
            unidades, "_aguardar_campos_dependentes"
        ), patch.object(unidades, "ActionChains", _Acoes), patch.object(unidades.time, "sleep"), patch.object(
            unidades, "_fechar_janelas_extras"
        ):
            unidades.executar(Mock(), Mock(), relatorio, self.contexto)

    def test_posicao_em_pelo_nome_vai_para_a_tela_em_toda_iteracao(self):
        # O catalogo pode usar outro identificador: o nome "Posição em" basta.
        filtro = {"nome": "Posição em", "campo_identificador": "dtPosicaoEm", "valor": "2026-09-30", "tipo_campo_valor": "DATE"}
        self._executar(self._relatorio(filtro))

        data = f"{unidades.POSICAO_EM_CAMPO}=30/09/2026"
        self.assertEqual(
            self.eventos,
            [
                data, "filter.empresa.cdEmpresaView=242", "cdEmpreendView=1002", "enter", "arquivo 242",
                data, "filter.empresa.cdEmpresaView=242", "cdEmpreendView=1003", "enter", "arquivo 242",
            ],
        )

    def test_posicao_em_pelo_campo_converte_data_mesmo_sem_tipo_date(self):
        filtro = {"nome": "Data", "campo_identificador": "filter.dtHistorica", "valor": "2026-08-31", "tipo_campo_valor": ""}
        self._executar(self._relatorio(filtro))

        self.assertIn(f"{unidades.POSICAO_EM_CAMPO}=31/08/2026", self.eventos)
        self.assertEqual(self.tela[unidades.POSICAO_EM_CAMPO], "31/08/2026")

    def test_data_que_nao_fica_na_tela_falha_antes_de_baixar(self):
        filtro = {"nome": "Posição em", "campo_identificador": "filter.dtHistorica", "valor": "2026-09-30", "tipo_campo_valor": "DATE"}
        with self.assertRaisesRegex(ValueError, "Posicao em .*'20/10/2026'.*'30/09/2026'"):
            self._executar(self._relatorio(filtro), tela_aceita_data=False)

        self.assertNotIn("enter", self.eventos)
        self.assertFalse([evento for evento in self.eventos if evento.startswith("arquivo")])

    def test_sem_posicao_em_mantem_a_data_padrao_do_sienge(self):
        self._executar(self._relatorio(None))

        self.assertFalse([evento for evento in self.eventos if evento.startswith(unidades.POSICAO_EM_CAMPO)])
        self.assertEqual(self.eventos.count("arquivo 242"), 2)

    def test_campos_que_nao_existem_na_tela_811_nao_sao_procurados(self):
        # A tela nao tem periodo nem "Tipo de relatorio": procurar custava 42 s por execucao.
        relatorio = self._relatorio(None)
        relatorio["filtros"].append({"nome": "Data inicial", "campo_identificador": "filter.dtInicioStr", "valor": "2026-09-01"})
        selecionar = Mock()
        self._executar(relatorio, selecionar=selecionar)
        selecionar.assert_called_once()
        self.assertEqual(selecionar.call_args.args[2], unidades.SELECAO_CAMPO)
        self.assertFalse([evento for evento in self.eventos if "dtInicioStr" in evento])
        self.assertEqual(self.eventos.count("arquivo 242"), 2)

    def test_posicao_em_vazio_nao_e_digitado(self):
        filtro = {"nome": "Posição em", "campo_identificador": "filter.dtHistorica", "valor": "", "tipo_campo_valor": "DATE"}
        self._executar(self._relatorio(filtro))

        self.assertEqual(self.tela[unidades.POSICAO_EM_CAMPO], "20/10/2026")
        self.assertEqual(self.eventos.count("enter"), 2)


if __name__ == "__main__":
    unittest.main()
