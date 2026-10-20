import unittest
from unittest.mock import patch

from selenium.common.exceptions import TimeoutException

from app_captacao.automacao import downloads, erros, execucao, login, navegador


class _FakeSwitchTo:
    def window(self, _handle):
        pass

    def default_content(self):
        pass


class _FakeDriver:
    window_handles = ["SIENGE"]
    current_window_handle = "SIENGE"

    def __init__(self):
        self.closed = False
        self.switch_to = _FakeSwitchTo()

    def execute_cdp_cmd(self, _comando, _parametros):
        return {"targetInfos": [{"targetId": "SIENGE", "url": "https://ebm.sienge.com.br/sienge/"}]}

    def quit(self):
        self.closed = True


class _DriverQueFalhaAoFechar(_FakeDriver):
    def quit(self):
        raise RuntimeError("browser already closed")


class _EdgeAnexadoFake(_FakeDriver):
    """Driver ligado ao Edge da automacao pela porta de depuracao: registra os comandos do DevTools."""

    def __init__(self, falha_ao_fechar_edge=False):
        super().__init__()
        self.comandos = []
        self._falha_ao_fechar_edge = falha_ao_fechar_edge
        navegador._drivers_edge_anexado.add(self)

    def execute_cdp_cmd(self, comando, parametros):
        self.comandos.append(comando)
        if comando == "Browser.close" and self._falha_ao_fechar_edge:
            raise RuntimeError("disconnected: not connected to DevTools")
        return super().execute_cdp_cmd(comando, parametros)


class ExecutionErrorMessageTests(unittest.TestCase):
    def test_remove_stacktrace_do_webdriver_da_mensagem_visivel(self):
        erro = TimeoutException("Message: campo indisponivel\nStacktrace:\nmsedgedriver!GetHandleVerifier")
        mensagem = erros.mensagem_erro_usuario(erro)
        self.assertEqual(mensagem, "campo indisponivel")
        self.assertNotIn("Stacktrace", mensagem)

    def test_timeout_sem_mensagem_recebe_texto_amigavel(self):
        mensagem = erros.mensagem_erro_usuario(TimeoutException())
        self.assertIn("Tempo esgotado", mensagem)


class SequenceExecutionTests(unittest.TestCase):
    def test_sequence_reports_partial_success_per_report(self):
        driver = _FakeDriver()
        reports = [
            {"id": 1, "nome": "Relatorio A", "operacao_nome": "Operacao X"},
            {"id": 2, "nome": "Relatorio B", "operacao_nome": "Operacao X"},
        ]

        def execute(_driver, _wait, report, _evento=None):
            if report["id"] == 2:
                raise erros.DownloadProcessingError("copia", "Destino indisponivel")
            return [r"C:\Destino\Relatorio_A.xlsx"]

        with patch.object(navegador, "criar_driver", return_value=driver), patch.object(
            login, "fazer_login"
        ), patch.object(execucao, "_executar_relatorio_no_driver", side_effect=execute), patch.object(
            downloads, "aguardar_pasta_download_estabilizar", return_value=True
        ), patch.object(execucao.time, "sleep"):
            result = execucao.executar_relatorios_em_sequencia("user", "password", reports)

        self.assertEqual(result["quantidade_baixados"], 1)
        self.assertEqual(result["quantidade_nao_baixados"], 1)
        self.assertEqual([item["estado"] for item in result["itens"]], ["baixado", "nao_baixado"])
        self.assertEqual(result["falhas"][0]["relatorio_nome"], "Relatorio B")
        self.assertEqual(result["falhas"][0]["etapa"], "copia")

    def test_authentication_failure_marks_all_reports_ignored(self):
        reports = [{"id": 1, "nome": "A"}, {"id": 2, "nome": "B"}]
        with patch.object(navegador, "criar_driver", return_value=_FakeDriver()), patch.object(
            login, "fazer_login", side_effect=RuntimeError("MFA pendente")
        ):
            result = execucao.executar_relatorios_em_sequencia("user", "password", reports)
        self.assertEqual([item["estado"] for item in result["itens"]], ["ignorado", "ignorado"])
        self.assertEqual(result["quantidade_nao_baixados"], 2)

    def test_falha_ao_fechar_o_navegador_nao_apaga_o_resultado(self):
        driver = _DriverQueFalhaAoFechar()
        with patch.object(navegador, "criar_driver", return_value=driver), patch.object(login, "fazer_login"), patch.object(
            execucao, "_executar_relatorio_no_driver", return_value=[r"C:\Destino\a.xlsx"]
        ), patch.object(execucao.time, "sleep"):
            result = execucao.executar_relatorios_em_sequencia("user", "password", [{"id": 1, "nome": "A"}])
        self.assertEqual(result["quantidade_baixados"], 1)


class LoteResilienteTests(unittest.TestCase):
    def test_sessao_que_cai_e_reaberta_e_os_relatorios_seguintes_rodam(self):
        reports = [{"id": 1, "nome": "A"}, {"id": 2, "nome": "B"}, {"id": 3, "nome": "C"}]
        drivers = [_FakeDriver(), _FakeDriver()]

        def execute(_driver, _wait, report, _evento=None):
            if report["id"] == 1:
                raise erros.DownloadProcessingError("execucao", "invalid session id")
            return [rf"C:\Downloads\Automacao CAP\{report['nome']}.xlsx"]

        with patch.object(navegador, "criar_driver", side_effect=drivers) as criar, patch.object(
            login, "fazer_login"
        ) as logar, patch.object(navegador, "definir_janela_principal"), patch.object(
            navegador, "voltar_para_janela_principal"
        ), patch.object(navegador, "sessao_do_driver_ativa", side_effect=[True, False, True]), patch.object(
            execucao, "_executar_relatorio_no_driver", side_effect=execute
        ), patch.object(downloads, "aguardar_pasta_download_estabilizar", return_value=True), patch.object(
            execucao.time, "sleep"
        ):
            result = execucao.executar_relatorios_em_sequencia("user", "password", reports)

        self.assertEqual(criar.call_count, 2)
        self.assertEqual(logar.call_count, 2)
        self.assertEqual([item["estado"] for item in result["itens"]], ["nao_baixado", "baixado", "baixado"])
        self.assertIn(r"C:\Downloads\Automacao CAP", result["resumo"])

    def test_sem_conseguir_reconectar_os_restantes_ficam_ignorados(self):
        reports = [{"id": 1, "nome": "A"}, {"id": 2, "nome": "B"}]
        with patch.object(navegador, "criar_driver", side_effect=[_FakeDriver(), RuntimeError("Edge fechado")]), patch.object(
            login, "fazer_login"
        ), patch.object(navegador, "definir_janela_principal"), patch.object(
            navegador, "sessao_do_driver_ativa", side_effect=[True, False]
        ), patch.object(execucao, "_executar_relatorio_no_driver", return_value=[r"C:\D\a.xlsx"]), patch.object(
            downloads, "aguardar_pasta_download_estabilizar", return_value=True
        ), patch.object(execucao.time, "sleep"):
            result = execucao.executar_relatorios_em_sequencia("user", "password", reports)
        estados = [(item["estado"], item["etapa"]) for item in result["itens"]]
        self.assertEqual(estados, [("baixado", ""), ("ignorado", "autenticacao")])

    def test_falha_no_meio_lista_os_arquivos_de_empresas_ja_salvas(self):
        relatorio = {"id": 1, "nome": "Analitico", "_arquivos_finais": [r"C:\D\Analitico_242_2026-10-15.xlsx"]}
        item = execucao._item_de_falha(relatorio, erros.DownloadProcessingError("download", "sem arquivo"))
        self.assertEqual(item["estado"], "nao_baixado")
        self.assertEqual(item["arquivos"], [r"C:\D\Analitico_242_2026-10-15.xlsx"])
        self.assertIn("Analitico_242_2026-10-15.xlsx", item["mensagem"])

    def test_relatorio_baixado_diz_onde_os_arquivos_ficaram(self):
        item = execucao._montar_item_resultado({"id": 1, "nome": "A"}, "baixado", arquivos=[r"C:\D\a.xlsx", r"C:\D\b.xlsx"])
        self.assertEqual(item["mensagem"], r"2 arquivo(s) salvo(s) em C:\D: a.xlsx, b.xlsx.")


class SingleReportExecutionTests(unittest.TestCase):
    def test_falha_de_login_no_relatorio_avulso_fica_ignorado_na_autenticacao(self):
        with patch.object(navegador, "criar_driver", return_value=_FakeDriver()), patch.object(
            login, "fazer_login", side_effect=RuntimeError("MFA pendente")
        ):
            result = execucao.executar_relatorio("user", "password", {"id": 1, "nome": "A"})
        item = result["itens"][0]
        self.assertEqual((item["estado"], item["etapa"]), ("ignorado", "autenticacao"))
        self.assertEqual(result["quantidade_nao_baixados"], 1)

    def test_falha_no_relatorio_avulso_fica_nao_baixado_com_a_etapa(self):
        with patch.object(navegador, "criar_driver", return_value=_FakeDriver()), patch.object(login, "fazer_login"), patch.object(
            execucao, "_executar_relatorio_no_driver", side_effect=erros.DownloadProcessingError("download", "sem arquivo")
        ), patch.object(execucao.time, "sleep"):
            result = execucao.executar_relatorio("user", "password", {"id": 1, "nome": "A"})
        item = result["itens"][0]
        self.assertEqual((item["estado"], item["etapa"]), ("nao_baixado", "download"))


class EncerramentoDoEdgeTests(unittest.TestCase):
    """No Edge anexado quit() so desconecta; o fim da execucao precisa fechar o Edge da automacao."""

    def _executar_operacao(self, drivers, reports, sessao_ativa=None):
        with patch.object(navegador, "criar_driver", side_effect=drivers), patch.object(login, "fazer_login"), patch.object(
            navegador, "definir_janela_principal"
        ), patch.object(navegador, "voltar_para_janela_principal"), patch.object(
            navegador, "sessao_do_driver_ativa", side_effect=sessao_ativa or [True] * len(reports)
        ), patch.object(execucao, "_executar_relatorio_no_driver", return_value=[r"C:\D\a.xlsx"]), patch.object(
            downloads, "aguardar_pasta_download_estabilizar", return_value=True
        ), patch.object(execucao.time, "sleep"):
            return execucao.executar_relatorios_em_sequencia("user", "password", reports)

    def test_fim_da_operacao_fecha_o_edge_anexado(self):
        driver = _EdgeAnexadoFake()
        result = self._executar_operacao([driver], [{"id": 1, "nome": "A"}])
        self.assertEqual(result["quantidade_baixados"], 1)
        self.assertIn("Browser.close", driver.comandos)
        self.assertTrue(driver.closed)

    def test_fim_do_relatorio_avulso_fecha_o_edge_anexado(self):
        driver = _EdgeAnexadoFake()
        with patch.object(navegador, "criar_driver", return_value=driver), patch.object(login, "fazer_login"), patch.object(
            navegador, "definir_janela_principal"
        ), patch.object(execucao, "_executar_relatorio_no_driver", return_value=[r"C:\D\a.xlsx"]), patch.object(
            downloads, "aguardar_pasta_download_estabilizar", return_value=True
        ), patch.object(execucao.time, "sleep"):
            result = execucao.executar_relatorio("user", "password", {"id": 1, "nome": "A"})
        self.assertEqual(result["quantidade_baixados"], 1)
        self.assertIn("Browser.close", driver.comandos)

    def test_sessao_que_cai_so_desconecta_e_o_edge_e_fechado_no_fim(self):
        caiu, reaberto = _EdgeAnexadoFake(), _EdgeAnexadoFake()
        reports = [{"id": 1, "nome": "A"}, {"id": 2, "nome": "B"}]
        result = self._executar_operacao([caiu, reaberto], reports, sessao_ativa=[True, False])
        self.assertEqual([item["estado"] for item in result["itens"]], ["baixado", "baixado"])
        self.assertNotIn("Browser.close", caiu.comandos)
        self.assertTrue(caiu.closed)
        self.assertIn("Browser.close", reaberto.comandos)

    def test_falha_ao_fechar_o_edge_ainda_encerra_a_sessao_e_mantem_o_resultado(self):
        driver = _EdgeAnexadoFake(falha_ao_fechar_edge=True)
        result = self._executar_operacao([driver], [{"id": 1, "nome": "A"}])
        self.assertEqual(result["quantidade_baixados"], 1)
        self.assertTrue(driver.closed)

    def test_navegador_proprio_do_selenium_nao_recebe_browser_close(self):
        driver = _FakeDriver()
        with patch.object(driver, "execute_cdp_cmd", wraps=driver.execute_cdp_cmd) as cdp:
            self._executar_operacao([driver], [{"id": 1, "nome": "A"}])
        self.assertNotIn("Browser.close", [chamada.args[0] for chamada in cdp.call_args_list])
        self.assertTrue(driver.closed)

    def test_keep_browser_open_deixa_o_edge_aberto(self):
        driver = _EdgeAnexadoFake()
        with patch.object(execucao, "KEEP_BROWSER_OPEN", True):
            self._executar_operacao([driver], [{"id": 1, "nome": "A"}])
        self.assertNotIn("Browser.close", driver.comandos)
        self.assertFalse(driver.closed)


class FiltroSemCampoNoSiengeTests(unittest.TestCase):
    """Filtro do cadastro sem campo na tela nunca e aplicado: avisa ou recusa, nunca passa calado."""

    def _relatorio(self):
        return {
            "id": 21,
            "nome": "Unidades",
            "url": "https://ebm.sienge.com.br/sienge/8/index.html#/common/page/811",
            "filtros": [
                {"id": 1, "nome": "Empresa", "campo_identificador": "filter.empresa.cdEmpresaView", "acao": "", "valor": "242"},
                {"id": 2, "nome": "Data inicial", "campo_identificador": "filter.dtInicioStr", "acao": "", "valor": "2026-09-01"},
            ],
        }

    def test_desligado_o_relatorio_roda_e_a_mensagem_lista_o_filtro(self):
        relatorio = self._relatorio()
        with patch.object(execucao.settings, "RECUSAR_FILTROS_SEM_CAMPO", False):
            execucao._conferir_filtros_aplicados(relatorio)
        item = execucao._montar_item_resultado(relatorio, "baixado", arquivos=[r"C:\x\Unidades\u.xlsx"])
        self.assertEqual(item["estado"], "baixado")
        self.assertIn("Não aplicado(s) no Sienge, sem campo na tela: Data inicial.", item["mensagem"])

    def test_ligado_recusa_antes_de_abrir_o_relatorio(self):
        aberturas = []
        with patch.object(execucao.settings, "RECUSAR_FILTROS_SEM_CAMPO", True), patch.object(
            navegador, "fechar_janelas_extras", lambda _driver: aberturas.append("janelas")
        ):
            with self.assertRaises(erros.DownloadProcessingError) as erro:
                execucao._executar_relatorio_no_driver(_FakeDriver(), None, self._relatorio())
        self.assertEqual(erro.exception.etapa, "configuracao")
        self.assertIn("Data inicial", str(erro.exception))
        self.assertEqual(aberturas, [])

    def test_ligado_sem_filtro_sobrando_nao_recusa(self):
        relatorio = self._relatorio()
        relatorio["filtros"].pop()
        with patch.object(execucao.settings, "RECUSAR_FILTROS_SEM_CAMPO", True):
            execucao._conferir_filtros_aplicados(relatorio)
        self.assertEqual(relatorio["_filtros_nao_aplicados"], [])


if __name__ == "__main__":
    unittest.main()
