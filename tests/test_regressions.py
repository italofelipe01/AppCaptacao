import time
import unittest
import uuid
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from app_core import app as app_module
from app_core import app_config
from services import automacao_service
from services.report_modules import extrato_saldo_devedor_presente as saldo_devedor


class _FakeCursor:
    def __init__(self, statements):
        self.statements = statements

    def execute(self, query, params=()):
        self.statements.append((" ".join(query.split()), tuple(params)))
        return self


class _FakeConnection:
    def __init__(self):
        self.statements = []
        self.committed = False

    def cursor(self):
        return _FakeCursor(self.statements)

    def commit(self):
        self.committed = True

    def close(self):
        pass


class _FakeDriver:
    def __init__(self):
        self.closed = False

    def quit(self):
        self.closed = True


class SaldoDevedorModalFiltersTests(unittest.TestCase):
    def setUp(self):
        self.driver = object()
        self.logger = unittest.mock.Mock()
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


class ExecutionErrorMessageTests(unittest.TestCase):
    def test_remove_stacktrace_do_webdriver_da_mensagem_visivel(self):
        erro = automacao_service.TimeoutException(
            "Message: campo indisponivel\nStacktrace:\nmsedgedriver!GetHandleVerifier"
        )
        mensagem = automacao_service._mensagem_erro_usuario(erro)
        self.assertEqual(mensagem, "campo indisponivel")
        self.assertNotIn("Stacktrace", mensagem)

    def test_timeout_sem_mensagem_recebe_texto_amigavel(self):
        mensagem = automacao_service._mensagem_erro_usuario(
            automacao_service.TimeoutException()
        )
        self.assertIn("Tempo esgotado", mensagem)


class OperationCreationTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app_module.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["user_login"] = "tester"
            session["user_access_id"] = 1

    def _request_patches(self):
        return patch.multiple(
            app_module,
            _safe_db_call=lambda loader, default: default,
            _log_config=lambda *args, **kwargs: None,
        )

    def test_rejects_operation_without_reports(self):
        with self._request_patches():
            response = self.client.post(
                "/acompanhamento/operacoes",
                data={"nome_operacao": "Operacao sem itens"},
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            messages = [message for _, message in session.get("_flashes", [])]
        self.assertTrue(any("pelo menos um relatorio" in message for message in messages))

    def test_creates_operation_and_links_in_submitted_order(self):
        connection = _FakeConnection()
        linked = []

        def insert_link(_connection, operation_id, report_id):
            linked.append((operation_id, report_id))

        with self._request_patches(), patch.object(app_module, "_db_connection", return_value=connection), patch.object(
            app_module, "_operation_name_exists", return_value=False
        ), patch.object(app_module, "_get_next_id", return_value=42), patch.object(
            app_module, "_column_exists", return_value=False
        ), patch.object(app_module, "_insert_operation_report_link", side_effect=insert_link):
            response = self.client.post(
                "/acompanhamento/operacoes",
                data={"nome_operacao": "Fechamento mensal", "id_relatorio": ["7", "2", "5"]},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(connection.committed)
        self.assertEqual(linked, [(42, 7), (42, 2), (42, 5)])
        self.assertIn("IdCapRecursoOperacoes", connection.statements[0][0])
        self.assertEqual(connection.statements[0][1][:2], (42, "Fechamento mensal"))

    def test_rejects_duplicate_active_name(self):
        connection = _FakeConnection()
        with self._request_patches(), patch.object(app_module, "_db_connection", return_value=connection), patch.object(
            app_module, "_operation_name_exists", return_value=True
        ):
            response = self.client.post(
                "/acompanhamento/operacoes",
                data={"nome_operacao": "Duplicada", "id_relatorio": "1"},
                follow_redirects=False,
            )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(connection.committed)

    def test_operation_payload_uses_link_order(self):
        captured = []

        def fake_fetch_all(query, params=()):
            captured.append(" ".join(query.split()))
            return []

        with patch.object(app_module, "_fetch_all", side_effect=fake_fetch_all), patch.object(
            app_module, "_db_connection", return_value=_FakeConnection()
        ), patch.object(app_module, "_get_filter_value_column", return_value=None), patch.object(
            app_module, "_column_exists", return_value=False
        ):
            self.assertEqual(app_module._load_relatorio_operacao_payload(9), [])
        self.assertIn("ORDER BY rxo.IdCapRecursoRelatorioOperacao", captured[0])


class UserManagementTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app_module.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["user_login"] = "admin"
            session["user_access_id"] = 1

    def test_user_listing_does_not_depend_on_access_table_column_names(self):
        captured = []

        def fake_fetch_all(query, params=()):
            captured.append(" ".join(query.split()))
            return [
                {
                    "id": 4,
                    "login": "operador",
                    "email": "operador@example.com",
                    "area": "captacao",
                    "access_id": 2,
                    "ativo": 1,
                    "data_criacao": None,
                }
            ]

        with patch.object(app_module, "_fetch_all", side_effect=fake_fetch_all):
            users = app_module._load_usuarios("", "ativos")

        self.assertNotIn("CapRecursoAcesso", captured[0])
        self.assertEqual(users[0]["id_acesso"], 2)
        self.assertEqual(users[0]["perfil"], "Usuario com cadastro de operacao")

    def test_user_page_renders_responsive_modals(self):
        with patch.object(app_module, "_load_user_by_id", return_value={
            "id": 10,
            "login": "admin",
            "email": "admin@example.com",
            "area": "ti",
            "access_id": 1,
            "ativo": 1,
            "data_criacao": None,
        }), patch.object(app_module, "_load_usuarios", return_value=[]):
            response = self.client.get("/usuarios")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"app-modal-overlay", response.data)
        self.assertIn(b"app-modal-body", response.data)

    def test_creates_user_with_explicit_id(self):
        connection = _FakeConnection()
        with patch.object(app_module, "_load_user_by_id", return_value={
            "id": 10,
            "login": "admin",
            "email": "admin@example.com",
            "area": "ti",
            "access_id": 1,
            "ativo": 1,
            "data_criacao": None,
        }), patch.object(app_module, "_db_connection", return_value=connection), patch.object(
            app_module, "_user_duplicate_field", return_value=None
        ), patch.object(app_module, "_column_is_identity", return_value=False), patch.object(
            app_module, "_get_next_id", return_value=21
        ), patch.object(
            app_module, "_log_config"
        ):
            response = self.client.post(
                "/usuarios",
                data={
                    "login_usuario": "novo.usuario",
                    "email": "novo@example.com",
                    "area": "captacao",
                    "id_acesso": "3",
                    "senha": "senha-segura",
                    "confirmar_senha": "senha-segura",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(connection.committed)
        self.assertIn("IdLogin", connection.statements[0][0])
        self.assertEqual(connection.statements[0][1][0], 21)

    def test_rejects_duplicate_user_without_committing(self):
        connection = _FakeConnection()
        with patch.object(app_module, "_load_user_by_id", return_value={
            "id": 10,
            "login": "admin",
            "email": "admin@example.com",
            "area": "ti",
            "access_id": 1,
            "ativo": 1,
            "data_criacao": None,
        }), patch.object(app_module, "_db_connection", return_value=connection), patch.object(
            app_module, "_user_duplicate_field", return_value="login"
        ):
            response = self.client.post(
                "/usuarios",
                data={
                    "login_usuario": "existente",
                    "email": "novo@example.com",
                    "area": "captacao",
                    "id_acesso": "3",
                    "senha": "senha-segura",
                    "confirmar_senha": "senha-segura",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(connection.committed)

    def test_rejects_user_without_password(self):
        with patch.object(app_module, "_load_user_by_id", return_value={
            "id": 10,
            "login": "admin",
            "email": "admin@example.com",
            "area": "ti",
            "access_id": 1,
            "ativo": 1,
            "data_criacao": None,
        }):
            response = self.client.post(
                "/usuarios",
                data={
                    "login_usuario": "novo.usuario",
                    "email": "novo@example.com",
                    "area": "captacao",
                    "id_acesso": "3",
                    "senha": "",
                    "confirmar_senha": "",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            messages = [message for _, message in session.get("_flashes", [])]
        self.assertTrue(any("obrigatorios" in message for message in messages))


class ExecutionResultTests(unittest.TestCase):
    def test_login_delegates_to_automatic_flow(self):
        driver = MagicMock()
        wait = MagicMock()
        with patch.object(
            automacao_service, "_restaurar_sessao_sienge", return_value=True
        ) as restaurar, patch.object(
            automacao_service, "_fazer_login_automatico"
        ) as login_automatico:
            automacao_service._fazer_login(driver, wait, "usuario@example.com", "senha")

        restaurar.assert_not_called()
        login_automatico.assert_called_once_with(
            driver, wait, "usuario@example.com", "senha"
        )

    def test_sso_frame_detach_falls_back_to_manual_token(self):
        driver = MagicMock()
        wait = MagicMock()
        with patch.object(
            automacao_service,
            "_fazer_login_automatico",
            side_effect=automacao_service.WebDriverException("target frame detached"),
        ), patch.object(
            automacao_service, "_aguardar_autenticacao_interativa", return_value=True
        ) as aguardar, patch.object(
            automacao_service, "_salvar_sessao_sienge"
        ) as salvar, patch.object(
            automacao_service, "SESSION_REUSE_ENABLED", True
        ):
            automacao_service._fazer_login(driver, wait, "usuario@example.com", "senha")

        aguardar.assert_called_once_with(driver, automacao_service.INTERACTIVE_LOGIN_TIMEOUT)
        salvar.assert_called_once_with(driver, "usuario@example.com")

    def test_session_is_not_active_while_login_control_is_visible(self):
        driver = MagicMock()
        driver.current_window_handle = "tab-2"
        driver.window_handles = ["tab-1", "tab-2"]
        driver.current_url = automacao_service.LOGIN_URL
        driver.execute_script.return_value = "complete"
        driver.find_elements.side_effect = lambda by, value: [object()] if value == "btnEntrarComSiengeID" else []

        self.assertFalse(automacao_service._sessao_sienge_ativa(driver))

    def test_session_is_active_only_on_loaded_sienge_page_without_login_controls(self):
        driver = MagicMock()
        driver.current_window_handle = "tab-2"
        driver.window_handles = ["tab-1", "tab-2"]
        driver.current_url = "https://ebm.sienge.com.br/sienge/8/index.html"
        driver.execute_script.return_value = "complete"
        driver.find_elements.return_value = []

        self.assertTrue(automacao_service._sessao_sienge_ativa(driver))

    def test_edge_failure_does_not_fall_back_to_chrome(self):
        with patch.object(automacao_service, "SELENIUM_BROWSER", "edge"), patch.object(
            automacao_service,
            "_criar_driver_edge",
            side_effect=RuntimeError("perfil Edge indisponivel"),
        ), patch.object(automacao_service, "_criar_driver_chrome") as criar_chrome, patch.object(
            automacao_service.Path, "mkdir"
        ):
            with self.assertRaisesRegex(RuntimeError, "perfil Edge indisponivel"):
                automacao_service._criar_driver()

        criar_chrome.assert_not_called()

    def test_sequence_reports_partial_success_per_report(self):
        driver = _FakeDriver()
        reports = [
            {"id": 1, "nome": "Relatorio A", "operacao_nome": "Operacao X"},
            {"id": 2, "nome": "Relatorio B", "operacao_nome": "Operacao X"},
        ]

        def execute(_driver, _wait, report):
            if report["id"] == 2:
                raise automacao_service.DownloadProcessingError("copia", "Destino indisponivel")
            return [r"C:\Destino\Relatorio_A.xlsx"]

        with patch.object(automacao_service, "_criar_driver", return_value=driver), patch.object(
            automacao_service, "_fazer_login"
        ), patch.object(automacao_service, "_executar_relatorio_no_driver", side_effect=execute), patch.object(
            automacao_service, "_aguardar_pasta_download_estabilizar", return_value=True
        ), patch.object(automacao_service.time, "sleep"):
            result = automacao_service.executar_relatorios_em_sequencia("user", "password", reports)

        self.assertEqual(result["quantidade_baixados"], 1)
        self.assertEqual(result["quantidade_nao_baixados"], 1)
        self.assertEqual([item["estado"] for item in result["itens"]], ["baixado", "nao_baixado"])
        self.assertEqual(result["falhas"][0]["relatorio_nome"], "Relatorio B")
        self.assertEqual(result["falhas"][0]["etapa"], "copia")

    def test_authentication_failure_marks_all_reports_ignored(self):
        reports = [{"id": 1, "nome": "A"}, {"id": 2, "nome": "B"}]
        with patch.object(automacao_service, "_criar_driver", return_value=_FakeDriver()), patch.object(
            automacao_service, "_fazer_login", side_effect=RuntimeError("MFA pendente")
        ):
            result = automacao_service.executar_relatorios_em_sequencia("user", "password", reports)
        self.assertEqual([item["estado"] for item in result["itens"]], ["ignorado", "ignorado"])
        self.assertEqual(result["quantidade_nao_baixados"], 2)

    def test_writable_state_falls_back_when_appdata_is_denied(self):
        fallback_dir = Path(tempfile.gettempdir()) / f"appcaptacao_state_test_{uuid.uuid4().hex}"
        denied_dir = fallback_dir.parent / f"denied_{uuid.uuid4().hex}"

        def ensure_directory(path):
            if Path(path) == denied_dir:
                raise PermissionError(5, "Acesso negado", str(path))
            Path(path).mkdir(parents=True, exist_ok=True)
            return Path(path)

        try:
            with patch.object(app_config, "get_state_dir", return_value=denied_dir), patch.object(
                app_config, "get_temporary_state_dir", return_value=fallback_dir
            ), patch.object(app_config, "_ensure_writable_directory", side_effect=ensure_directory):
                self.assertEqual(app_config.get_writable_state_dir(), fallback_dir)
        finally:
            if fallback_dir.exists():
                fallback_dir.rmdir()

    def test_download_watcher_does_not_reuse_preexisting_file(self):
        directory = Path(__file__).parent
        old_file = directory / f"relatorio_antigo_{uuid.uuid4().hex}.xlsx"
        try:
            old_file.write_bytes(b"old")
            with patch.object(automacao_service, "DOWNLOAD_DIR", str(directory)), patch.object(
                automacao_service, "DOWNLOAD_WAIT_TIMEOUT", 0.08
            ), patch.object(automacao_service, "DOWNLOAD_STABLE_CHECK_INTERVAL", 0.01):
                marker = automacao_service._marcar_inicio_download()
                result = automacao_service._aguardar_arquivo_download(marker)
        finally:
            old_file.unlink(missing_ok=True)
        self.assertEqual(result, "")

    def test_download_watcher_accepts_only_a_new_stable_file(self):
        directory = Path(__file__).parent
        new_file = directory / f"novo_{uuid.uuid4().hex}.xlsx"
        try:
            with patch.object(automacao_service, "DOWNLOAD_DIR", str(directory)), patch.object(
                automacao_service, "DOWNLOAD_WAIT_TIMEOUT", 0.3
            ), patch.object(automacao_service, "DOWNLOAD_STABLE_CHECK_INTERVAL", 0.01), patch.object(
                automacao_service, "DOWNLOAD_STABLE_CYCLES_REQUIRED", 2
            ):
                marker = automacao_service._marcar_inicio_download()
                time.sleep(0.002)
                new_file.write_bytes(b"complete")
                result = automacao_service._aguardar_arquivo_download(marker)
        finally:
            new_file.unlink(missing_ok=True)
        self.assertEqual(result, new_file)


class BackgroundExecutionTests(unittest.TestCase):
    def setUp(self):
        app_module.app.config.update(TESTING=True, SECRET_KEY="test")
        app_module._execution_jobs.clear()

    def test_job_tracks_each_report_until_partial_result(self):
        reports = [
            {"id": 1, "nome": "Relatorio A", "operacao_nome": "Operacao X"},
            {"id": 2, "nome": "Relatorio B", "operacao_nome": "Operacao X"},
        ]
        with app_module.app.test_request_context("/"):
            job_id = app_module._create_execution_job("operacao", reports, "Operacao X")

        result = {
            "itens": [
                {
                    "relatorio_id": 1,
                    "relatorio_nome": "Relatorio A",
                    "operacao_nome": "Operacao X",
                    "estado": "baixado",
                    "mensagem": "",
                    "etapa": "",
                    "caminho_final": r"C:\Destino\a.xlsx",
                    "arquivos": [r"C:\Destino\a.xlsx"],
                },
                {
                    "relatorio_id": 2,
                    "relatorio_nome": "Relatorio B",
                    "operacao_nome": "Operacao X",
                    "estado": "nao_baixado",
                    "mensagem": "Falha ao copiar",
                    "etapa": "copia",
                    "caminho_final": "",
                    "arquivos": [],
                },
            ],
            "sucessos": [{}],
            "falhas": [{}],
            "quantidade_baixados": 1,
            "quantidade_nao_baixados": 1,
            "resumo": "1 relatorio baixado; 1 nao baixado.",
        }

        def fake_sequence(_email, _senha, _reports, on_report_event=None):
            on_report_event("processando", reports[0], {})
            on_report_event(
                "sucesso",
                reports[0],
                {"caminho_final": r"C:\Destino\a.xlsx", "arquivos": [r"C:\Destino\a.xlsx"]},
            )
            on_report_event("processando", reports[1], {})
            on_report_event("erro", reports[1], {"mensagem": "Falha ao copiar", "etapa": "copia"})
            return result

        with patch.object(app_module, "executar_relatorios_em_sequencia", side_effect=fake_sequence), patch.object(
            app_module, "_log_operacao"
        ):
            app_module._run_execution_job(
                job_id,
                "operacao",
                "user",
                "password",
                reports,
                {"login": "tester"},
                "Operacao X",
            )

        job = app_module._execution_jobs[job_id]
        self.assertEqual(job["estado"], "concluida")
        self.assertEqual(job["quantidade_baixados"], 1)
        self.assertEqual(job["quantidade_nao_baixados"], 1)
        self.assertEqual([item["estado"] for item in job["itens"]], ["baixado", "nao_baixado"])


if __name__ == "__main__":
    unittest.main()
