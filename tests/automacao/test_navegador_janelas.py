import unittest

from selenium.common.exceptions import InvalidSessionIdException, WebDriverException

from app_captacao.automacao import navegador

SIENGE = "A1" * 16
DIALOGO = "B2" * 16
POPUP = "C3" * 16


class _SwitchTo:
    def __init__(self, driver):
        self._driver = driver

    def window(self, handle):
        if handle not in self._driver.janelas:
            raise WebDriverException("no such window")
        self._driver.atual = handle

    def default_content(self):
        pass

    def new_window(self, _tipo):
        self._driver.janelas["NOVA"] = "about:blank"
        self._driver.atual = "NOVA"


class _EdgeAnexado:
    """Edge anexado pela porta de depuracao: o DevTools lista tambem o dialogo interno."""

    def __init__(self, atual=SIENGE):
        self.janelas = {
            SIENGE: "https://ebm.sienge.com.br/sienge/8/index.html#/common/page/473",
            DIALOGO: "edge://sync-confirmation-dialog/",
            POPUP: "https://ebm.sienge.com.br/sienge/relatorio.do",
        }
        self.atual = atual
        self.fechadas = []
        self.switch_to = _SwitchTo(self)

    @property
    def window_handles(self):
        return list(self.janelas)

    @property
    def current_window_handle(self):
        return self.atual

    @property
    def current_url(self):
        return self.janelas[self.atual]

    def execute_cdp_cmd(self, comando, _parametros):
        assert comando == "Target.getTargets"
        return {"targetInfos": [{"targetId": handle, "type": "page", "url": url} for handle, url in self.janelas.items()]}

    def close(self):
        if self.janelas[self.atual].startswith("edge://"):
            raise WebDriverException("unknown error: failed to close window in 20 seconds")
        self.fechadas.append(self.atual)
        del self.janelas[self.atual]

    def maximize_window(self):
        pass


class FecharJanelasTests(unittest.TestCase):
    def test_fecha_so_o_popup_e_nunca_o_dialogo_interno(self):
        driver = _EdgeAnexado()
        navegador.definir_janela_principal(driver)
        navegador.fechar_janelas_extras(driver)
        self.assertEqual(driver.fechadas, [POPUP])
        self.assertIn(DIALOGO, driver.janelas)
        self.assertEqual(driver.atual, SIENGE)

    def test_driver_parado_no_dialogo_nao_fecha_a_aba_do_sienge(self):
        # Cenario do log: depois de uma falha a janela "atual" era o dialogo interno.
        driver = _EdgeAnexado(atual=DIALOGO)
        navegador.definir_janela_principal(driver)  # nao aceita o dialogo como principal
        navegador.fechar_janelas_extras(driver)
        self.assertIn(SIENGE, driver.janelas)
        self.assertEqual(driver.fechadas, [POPUP])
        self.assertEqual(driver.atual, SIENGE)

    def test_aba_principal_fechada_escolhe_outra_aba_do_sienge(self):
        driver = _EdgeAnexado()
        navegador.definir_janela_principal(driver)
        del driver.janelas[SIENGE]
        navegador.voltar_para_janela_principal(driver)
        self.assertEqual(driver.atual, POPUP)


class SessaoTests(unittest.TestCase):
    def test_sessao_invalida_e_detectada(self):
        class _SessaoMorta:
            @property
            def window_handles(self):
                raise InvalidSessionIdException("invalid session id")

        self.assertFalse(navegador.sessao_do_driver_ativa(_SessaoMorta()))
        self.assertTrue(navegador.sessao_do_driver_ativa(_EdgeAnexado()))


if __name__ == "__main__":
    unittest.main()
