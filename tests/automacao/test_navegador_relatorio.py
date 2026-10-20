"""Abertura da tela do relatorio: iframe certo e espera pelo formulario, nao por pausa fixa.

Medido no Sienge em 2026-10-20: o formulario fica pronto 0,4-0,6 s depois da navegacao, e a
pagina tem iframes de widgets (novidades, chat) alem do iframe do relatorio (iFramePage).
"""

import unittest
from unittest.mock import patch

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from app_captacao.automacao import navegador


class _Relogio:
    def __init__(self):
        self.agora = 0.0

    def __call__(self):
        return self.agora


class _Quadro:
    def __init__(self, id_):
        self.id_ = id_


class _PaginaComWidgets:
    """Iframes da pagina por instante: o do relatorio pode aparecer depois dos widgets."""

    def __init__(self, relogio, iframe_do_relatorio_em=None):
        self.relogio = relogio
        self.iframe_do_relatorio_em = iframe_do_relatorio_em

    def _quadros(self):
        quadros = []
        if self.iframe_do_relatorio_em is not None and self.relogio.agora >= self.iframe_do_relatorio_em:
            quadros.append(_Quadro(navegador.IFRAME_DO_RELATORIO))
        return [*quadros, _Quadro("beamerUtilities"), _Quadro("fc_widget")]

    def find_elements(self, by, valor):
        quadros = self._quadros()
        return [quadro for quadro in quadros if quadro.id_ == valor] if by == By.ID else quadros


class _EsperaFalsa:
    def __init__(self, driver, relogio, passos=40):
        self.driver, self.relogio, self.passos = driver, relogio, passos

    def until(self, condicao):
        for _ in range(self.passos):
            resultado = condicao(self.driver)
            if resultado:
                return resultado
            self.relogio.agora += 0.5
        raise TimeoutException()


class IframeDoRelatorioTests(unittest.TestCase):
    def _localizar(self, iframe_do_relatorio_em):
        relogio = _Relogio()
        pagina = _PaginaComWidgets(relogio, iframe_do_relatorio_em)
        with patch.object(navegador.time, "monotonic", relogio):
            return navegador.iframe_do_relatorio(pagina, _EsperaFalsa(pagina, relogio)).id_

    def test_widget_que_carrega_antes_nao_e_confundido_com_o_relatorio(self):
        self.assertEqual(self._localizar(iframe_do_relatorio_em=2.0), navegador.IFRAME_DO_RELATORIO)

    def test_tela_sem_iframe_do_relatorio_usa_o_primeiro_como_antes(self):
        self.assertEqual(self._localizar(iframe_do_relatorio_em=None), "beamerUtilities")


class _DriverDoSienge:
    def __init__(self, url_atual, pronto_na_consulta: int | None = 1):
        self.current_url = url_atual
        self.eventos = []
        self.consultas = 0
        self.pronto_na_consulta = pronto_na_consulta
        outer = self

        class _Troca:
            def default_content(self):
                outer.eventos.append("default_content")

        self.switch_to = _Troca()

    def execute_script(self, script, *_args):
        if "setAttribute" in script:
            self.eventos.append("marca iframe anterior")
            return None
        self.consultas += 1
        return self.pronto_na_consulta is not None and self.consultas >= self.pronto_na_consulta

    def get(self, url):
        self.eventos.append(f"get {url}")

    def refresh(self):
        self.eventos.append("refresh")


class AbrirRelatorioTests(unittest.TestCase):
    URL = "https://ebm.sienge.com.br/sienge/8/index.html#/common/page/811"

    def _abrir(self, driver, timeout: float = 2):
        with patch.object(navegador.time, "sleep") as pausa:
            pronta = navegador.abrir_relatorio(driver, self.URL, timeout=timeout)
        return pronta, pausa

    def test_marca_a_tela_anterior_antes_de_navegar_e_espera_o_formulario(self):
        driver = _DriverDoSienge("https://ebm.sienge.com.br/sienge/8/index.html#/common/page/708", pronto_na_consulta=2)
        pronta, pausa = self._abrir(driver)
        self.assertTrue(pronta)
        self.assertEqual(driver.eventos[-2:], ["marca iframe anterior", f"get {self.URL}"])
        self.assertGreaterEqual(driver.consultas, 2)
        # A ultima pausa e a folga para os scripts da tela; as outras sao as consultas da espera.
        self.assertEqual(pausa.call_args.args, (navegador.PAUSA_APOS_TELA_PRONTA,))

    def test_mesma_url_recarrega_para_o_formulario_vir_limpo(self):
        driver = _DriverDoSienge(self.URL)
        self._abrir(driver)
        self.assertIn("refresh", driver.eventos)
        self.assertFalse([evento for evento in driver.eventos if evento.startswith("get")])

    def test_formulario_que_nao_fica_pronto_segue_depois_do_limite(self):
        driver = _DriverDoSienge("https://x/#/common/page/708", pronto_na_consulta=None)
        with self.assertLogs(navegador.logger, "WARNING") as aviso:
            pronta, _ = self._abrir(driver, timeout=0.3)
        self.assertFalse(pronta)
        self.assertIn("nao ficou pronta", aviso.output[0])


if __name__ == "__main__":
    unittest.main()
