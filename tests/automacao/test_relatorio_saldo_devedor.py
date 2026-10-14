import unittest
from unittest.mock import MagicMock, Mock, patch

from app_captacao.automacao.relatorios.executores import extrato_saldo_devedor_presente as saldo_devedor


class SaldoDevedorModalFiltersTests(unittest.TestCase):
    def setUp(self):
        self.driver = object()
        self.logger = Mock()
        self.filtro_empresa = {"campo_identificador": "cdEmpresaView", "valor": ["1", "2"]}
        self.filtro_data_inicio = {"campo_identificador": "dtInicio", "valor": "2026-09-01"}
        self.filtro_data_fim = {"campo_identificador": "dtFim", "valor": "2026-09-30"}
        self.filtro_data_correcao = {"campo_identificador": "dtCorrecao", "valor": "2026-09-30"}
        self.filtro_data_posicao = {"campo_identificador": "dtPosicao", "valor": "2026-09-30"}

    @staticmethod
    def _normalizar(filtro):
        return str(filtro.get("valor") or "")

    def _executar_preparacao(self, index, eventos):
        with patch.object(saldo_devedor, "_preencher_input_manual", return_value="data"), patch.object(
            saldo_devedor,
            "_preencher_autocomplete_empresa",
            side_effect=lambda *args, **kwargs: eventos.append("empresa") or "empresa",
        ), patch.object(
            saldo_devedor,
            "_aplicar_datas_modal",
            side_effect=lambda *args, **kwargs: eventos.append("aplicar_modal"),
        ), patch.object(
            saldo_devedor,
            "_clicar_botao_consultar",
            side_effect=lambda *args, **kwargs: eventos.append("consultar"),
        ), patch.object(saldo_devedor, "_aguardar_grade_pronta"), patch.object(
            saldo_devedor, "_log_etapa"
        ):
            saldo_devedor._preparar_filtros_relatorio(
                self.driver,
                None,
                self._normalizar,
                lambda *args, **kwargs: "",
                self.filtro_empresa,
                "1" if index == 0 else "2",
                self.filtro_data_inicio,
                self.filtro_data_fim,
                self.filtro_data_correcao,
                self.filtro_data_posicao,
                self.logger,
                index,
                2,
                lambda *args: None,
            )

    def test_primeira_empresa_aplica_datas_modal_sem_clicar_consultar(self):
        eventos = []
        self._executar_preparacao(0, eventos)
        self.assertEqual(eventos, ["empresa", "aplicar_modal"])

    def test_empresa_seguinte_reutiliza_datas_e_clica_consultar(self):
        eventos = []
        self._executar_preparacao(1, eventos)
        self.assertEqual(eventos, ["empresa", "consultar"])

    def test_localiza_datas_pela_ordem_dos_inputs_visiveis_da_modal(self):
        correcao = MagicMock(id="correcao")
        posicao = MagicMock(id="posicao")
        correcao.is_displayed.return_value = True
        correcao.is_enabled.return_value = True
        posicao.is_displayed.return_value = True
        posicao.is_enabled.return_value = True
        driver = MagicMock()

        def find_elements(by, seletor):
            if by == saldo_devedor.By.CSS_SELECTOR and seletor == "[role='dialog'] input":
                return [correcao, posicao]
            return []

        driver.find_elements.side_effect = find_elements
        localizado = saldo_devedor._localizar_input_modal(
            driver,
            "data_posicao",
            saldo_devedor.XPATH_DATA_POSICAO_MODAL,
            "Posicao em",
            1,
        )
        self.assertIs(localizado, posicao)

    def test_erro_modal_identifica_etapa_para_resultado(self):
        erro = saldo_devedor.ModalDatasError("campo nao localizado")
        self.assertEqual(erro.etapa, "preenchimento_modal")

    def test_falha_apos_avancar_pagina_nao_clica_novamente(self):
        botao = MagicMock()
        botao.tag_name = "button"
        driver = MagicMock()
        espera = MagicMock()
        espera.until.return_value = botao

        with patch.object(saldo_devedor, "WebDriverWait", return_value=espera), patch.object(
            saldo_devedor, "_obter_texto_paginacao_atual", return_value="1-5000 de 7000"
        ), patch.object(
            saldo_devedor, "_aguardar_grade_pronta", side_effect=TimeoutError("grade nao mudou")
        ):
            with self.assertRaises(TimeoutError):
                saldo_devedor._ir_para_proxima_pagina(driver, self.logger)

        botao.click.assert_called_once_with()

    def test_exporta_duas_paginas_sem_fechar_aba_do_relatorio(self):
        driver = MagicMock()
        renomear = MagicMock(side_effect=["pagina_1.xlsx", "pagina_2.xlsx"])
        avancar = MagicMock()
        contexto = {
            "logger": self.logger,
            "normalizar_valor": self._normalizar,
            "preencher_autocomplete_enter": MagicMock(),
            "marcar_inicio_download": MagicMock(return_value={}),
            "renomear_download": renomear,
            "sanitizar_nome_arquivo": MagicMock(),
            "copiar_download_para_sharepoint": MagicMock(),
            "montar_caminho_download_unico": MagicMock(),
            "capture_debug_snapshot": MagicMock(),
            "download_dir": ".",
        }

        with patch.multiple(
            saldo_devedor,
            _aguardar_tela_filtros=MagicMock(),
            _preparar_filtros_relatorio=MagicMock(),
            _selecionar_tamanho_pagina=MagicMock(),
            _obter_total_registros=MagicMock(return_value=7000),
            _clicar_botao_gerar_relatorio=MagicMock(),
            _selecionar_formato_excel_na_modal=MagicMock(),
            _consolidar_planilhas=MagicMock(return_value=None),
            _ir_para_proxima_pagina=avancar,
            _aguardar_grade_pronta=MagicMock(),
        ), patch.object(saldo_devedor.time, "sleep"):
            saldo_devedor.executar(driver, None, {"filtros": []}, contexto)

        self.assertEqual(renomear.call_count, 2)
        avancar.assert_called_once_with(driver, self.logger)
        driver.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
