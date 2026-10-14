from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pyodbc
from werkzeug.security import check_password_hash

import app as legacy_app


class DesktopAppError(Exception):
    pass


class DesktopPermissionError(DesktopAppError):
    pass


@dataclass
class DesktopBackend:
    current_user: dict[str, Any] | None = None
    execution_credentials: dict[str, str] = field(
        default_factory=lambda: {
            "email": "",
            "senha": "",
            "sharepoint_link": "",
        }
    )

    def _apply_session_state(self) -> None:
        legacy_app.session.clear()
        if not self.current_user:
            return

        legacy_app.session["user_id"] = self.current_user["id"]
        legacy_app.session["user_login"] = self.current_user["login"]
        legacy_app.session["user_email"] = self.current_user["email"]
        legacy_app.session["user_area"] = self.current_user["area"]
        legacy_app.session["user_access_id"] = self.current_user["access_id"]
        legacy_app.session["execucao_email"] = self.execution_credentials.get("email", "")
        legacy_app.session["execucao_senha"] = self.execution_credentials.get("senha", "")
        legacy_app.session["execucao_sharepoint_link"] = self.execution_credentials.get("sharepoint_link", "")

    def _capture_session_state(self) -> None:
        if not self.current_user:
            self.execution_credentials = {
                "email": "",
                "senha": "",
                "sharepoint_link": "",
            }
            return

        self.execution_credentials = {
            "email": legacy_app.session.get("execucao_email", ""),
            "senha": legacy_app.session.get("execucao_senha", ""),
            "sharepoint_link": legacy_app.session.get("execucao_sharepoint_link", ""),
        }

    def _run(self, func: Callable[..., Any], *args: Any, path: str = "/desktop", method: str = "GET") -> Any:
        with legacy_app.app.test_request_context(path, method=method):
            self._apply_session_state()
            result = func(*args)
            self._capture_session_state()
            return result

    def _require_login(self) -> None:
        if not self.current_user:
            raise DesktopPermissionError("Faça login para continuar.")

    def _require_access(self, *allowed_access_ids: int) -> None:
        self._require_login()
        if self.current_user["access_id"] not in allowed_access_ids:
            raise DesktopPermissionError("Seu perfil não possui permissão para esta ação.")

    def login(self, login_usuario: str, senha: str) -> dict[str, Any]:
        login_usuario = str(login_usuario or "").strip()
        senha = str(senha or "")
        payload_login = {"login_informado": login_usuario}

        if not login_usuario or not senha:
            raise DesktopAppError("Informe login e senha para entrar.")

        bootstrap_admin = legacy_app.get_bootstrap_admin()

        def _do_login() -> dict[str, Any]:
            try:
                usuario = legacy_app.buscar_usuario_por_login(login_usuario)
            except pyodbc.Error:
                usuario = None
                if not (
                    bootstrap_admin
                    and login_usuario == bootstrap_admin["login"]
                    and bootstrap_admin["password_hash"]
                    and check_password_hash(bootstrap_admin["password_hash"], senha)
                ):
                    try:
                        legacy_app.registrar_log_acesso(
                            "login_falha",
                            "Erro ao validar login no banco de dados.",
                            payload=payload_login,
                            usuario={"login": login_usuario},
                        )
                    except pyodbc.Error:
                        pass
                    raise DesktopAppError("Não foi possível validar o login no banco de dados.")

            if (
                not usuario
                and bootstrap_admin
                and login_usuario == bootstrap_admin["login"]
                and bootstrap_admin["password_hash"]
                and check_password_hash(bootstrap_admin["password_hash"], senha)
            ):
                user = {
                    "id": int(bootstrap_admin["id"]),
                    "login": bootstrap_admin["login"],
                    "email": bootstrap_admin["email"],
                    "area": bootstrap_admin["area"],
                    "access_id": int(bootstrap_admin["access_id"]),
                }
                self.current_user = user
                legacy_app.registrar_log_acesso(
                    "login",
                    "Login realizado com admin local de desenvolvimento.",
                    payload=payload_login,
                )
                return user

            if not usuario or not usuario.IdAtivo:
                try:
                    legacy_app.registrar_log_acesso(
                        "login_falha",
                        "Usuario inexistente ou inativo.",
                        payload=payload_login,
                        usuario={"login": login_usuario},
                    )
                except pyodbc.Error:
                    pass
                raise DesktopAppError("Usuário ou senha inválidos.")

            if not check_password_hash(usuario.Senha, senha):
                try:
                    legacy_app.registrar_log_acesso(
                        "login_falha",
                        "Senha invalida.",
                        payload=payload_login,
                        usuario={
                            "id": int(usuario.IdLogin),
                            "login": usuario.Login,
                            "email": usuario.Email,
                            "area": usuario.Area,
                            "access_id": int(usuario.IdAcesso),
                        },
                    )
                except pyodbc.Error:
                    pass
                raise DesktopAppError("Usuário ou senha inválidos.")

            user = {
                "id": int(usuario.IdLogin),
                "login": usuario.Login,
                "email": usuario.Email,
                "area": usuario.Area,
                "access_id": int(usuario.IdAcesso),
            }
            self.current_user = user
            legacy_app.registrar_log_acesso(
                "login",
                "Login realizado com sucesso.",
                payload=payload_login,
            )
            return user

        return self._run(_do_login, path="/desktop/login", method="POST")

    def logout(self) -> None:
        if self.current_user:
            try:
                self._run(legacy_app.registrar_log_acesso, "logout", "Sessao encerrada com sucesso.", path="/desktop/logout")
            except pyodbc.Error:
                pass
        self.current_user = None
        self.execution_credentials = {
            "email": "",
            "senha": "",
            "sharepoint_link": "",
        }

    def get_dashboard_data(self) -> dict[str, Any]:
        self._require_login()
        return {
            "relatorios_disponiveis": self._run(legacy_app.listar_relatorios_disponiveis, path="/desktop/dashboard"),
            "operacoes_disponiveis": self._run(legacy_app.listar_operacoes_execucao, path="/desktop/dashboard"),
            "credenciais_execucao": dict(self.execution_credentials),
        }

    def get_relatorio_config(self, id_relatorio: int) -> dict[str, Any]:
        self._require_login()
        relatorio = self._run(legacy_app.buscar_relatorio_com_filtros, id_relatorio, path=f"/desktop/relatorios/{id_relatorio}")
        if not relatorio:
            raise DesktopAppError("Relatório não encontrado.")

        for filtro in relatorio.get("filtros", []):
            filtro["opcional"] = legacy_app.eh_filtro_opcional_relatorio(relatorio, filtro)
        return relatorio

    def get_operacao_config(self, operacao_id: int) -> list[dict[str, Any]]:
        self._require_login()

        def _load() -> list[dict[str, Any]]:
            if not legacy_app.usuario_pode_acessar_operacao(operacao_id):
                raise DesktopPermissionError("Você não possui permissão para executar esta operação.")
            return legacy_app.montar_relatorios_operacao_execucao(operacao_id)

        return self._run(_load, path=f"/desktop/operacoes/{operacao_id}")

    def execute_relatorio(self, payload: dict[str, Any]) -> str:
        self._require_access(legacy_app.ACESSO_ADMIN, legacy_app.ACESSO_OPERACAO, legacy_app.ACESSO_EXECUCAO)

        email = legacy_app.obter_texto(payload, "email")
        senha = str(payload.get("senha", ""))
        sharepoint_link = legacy_app.obter_texto(payload, "sharepoint_link")
        data_periodo = legacy_app.obter_texto(payload, "data_periodo") or legacy_app.obter_texto(payload, "data")
        raw_id_relatorio = legacy_app.obter_texto(payload, "relatorio") or legacy_app.obter_texto(payload, "relatorio_id")

        if not email or not senha or not raw_id_relatorio:
            raise DesktopAppError("Preencha email, senha e relatório para continuar.")

        id_relatorio = int(raw_id_relatorio)
        self.execution_credentials = {
            "email": email,
            "senha": senha,
            "sharepoint_link": sharepoint_link,
        }

        def _execute() -> str:
            relatorio = legacy_app.buscar_relatorio_com_filtros(id_relatorio)
            if not relatorio:
                raise DesktopAppError("O relatório selecionado não foi encontrado.")

            valores_filtros = legacy_app.coletar_valores_filtros(relatorio, payload)
            valores_filtros.setdefault("filtro_data_periodo", data_periodo)
            campos_pendentes = legacy_app.validar_filtros_preenchidos(relatorio, valores_filtros)
            if campos_pendentes:
                raise DesktopAppError(
                    "Preencha os filtros do relatório antes de executar: " + ", ".join(campos_pendentes) + "."
                )

            relatorio_execucao = legacy_app.montar_payload_execucao(id_relatorio, valores_filtros)
            relatorio_execucao["sharepoint_link"] = sharepoint_link
            resumo_filtros_log = legacy_app.resumir_filtros_para_log(relatorio_execucao.get("filtros", []))
            payload_log_execucao = {
                "tipo_execucao": "relatorio",
                "modo_execucao": "completo",
                "relatorio": relatorio_execucao,
                "resumo_filtros": resumo_filtros_log,
                "email_execucao": email,
                "sharepoint_link": sharepoint_link,
                "data_periodo": data_periodo,
            }

            log_execucao_id = None
            try:
                log_execucao_id = legacy_app.criar_log_execucao(
                    "relatorio",
                    "completo",
                    "aguardando",
                    payload_entrada=payload_log_execucao,
                    id_relatorio=relatorio_execucao.get("id"),
                    nome_relatorio=relatorio_execucao.get("nome"),
                    observacao="Execucao de relatorio solicitada pelo aplicativo desktop.",
                )
            except pyodbc.Error:
                pass

            legacy_app.iniciar_execucao_automacao(email, senha, relatorio_execucao, log_execucao_id=log_execucao_id)
            return (
                f"Automação iniciada para o relatório {relatorio_execucao['nome']} "
                f"com {len(relatorio_execucao['filtros'])} filtro(s)."
            )

        return self._run(_execute, path="/desktop/executar-relatorio", method="POST")

    def execute_operacao(self, payload: dict[str, Any]) -> str:
        self._require_access(legacy_app.ACESSO_ADMIN, legacy_app.ACESSO_OPERACAO, legacy_app.ACESSO_EXECUCAO)

        email = legacy_app.obter_texto(payload, "email")
        senha = str(payload.get("senha", ""))
        sharepoint_link = legacy_app.obter_texto(payload, "sharepoint_link")
        raw_id_operacao = legacy_app.obter_texto(payload, "operacao") or legacy_app.obter_texto(payload, "operacao_id")

        if not email or not senha or not raw_id_operacao:
            raise DesktopAppError("Preencha email, senha e operação para continuar.")

        id_operacao = int(raw_id_operacao)
        self.execution_credentials = {
            "email": email,
            "senha": senha,
            "sharepoint_link": sharepoint_link,
        }

        def _execute() -> str:
            if not legacy_app.usuario_pode_acessar_operacao(id_operacao):
                raise DesktopPermissionError("Você não possui permissão para executar esta operação.")

            relatorios_execucao = legacy_app.montar_relatorios_operacao_execucao(id_operacao)
            if not relatorios_execucao:
                raise DesktopAppError("A operação selecionada não possui relatórios ativos vinculados.")

            nome_operacao_execucao = next(
                (
                    item["nome"]
                    for item in legacy_app.listar_operacoes_execucao()
                    if int(item["id"]) == id_operacao
                ),
                f"Operacao {id_operacao}",
            )

            pendencias = []
            for relatorio in relatorios_execucao:
                relatorio["nome_operacao"] = nome_operacao_execucao
                relatorio["sharepoint_link"] = sharepoint_link
                campos_pendentes = legacy_app.validar_filtros_preenchidos(
                    relatorio,
                    {f"filtro_{filtro['id']}": filtro.get("valor") for filtro in relatorio.get("filtros", [])},
                )
                if campos_pendentes:
                    pendencias.append(f"{relatorio['nome']}: " + ", ".join(campos_pendentes))

            if pendencias:
                raise DesktopAppError(
                    "Preencha os valores dos filtros da operação antes de executar: " + "; ".join(pendencias) + "."
                )

            resumo_relatorios_log = [
                {
                    "id": relatorio.get("id"),
                    "nome": relatorio.get("nome"),
                    "resumo_filtros": legacy_app.resumir_filtros_para_log(relatorio.get("filtros", [])),
                }
                for relatorio in relatorios_execucao
            ]
            payload_log_execucao = {
                "tipo_execucao": "operacao",
                "modo_execucao": "parceiros",
                "operacao_id": id_operacao,
                "operacao_nome": nome_operacao_execucao,
                "email_execucao": email,
                "sharepoint_link": sharepoint_link,
                "relatorios": resumo_relatorios_log,
            }

            log_execucao_id = None
            try:
                log_execucao_id = legacy_app.criar_log_execucao(
                    "operacao",
                    "parceiros",
                    "aguardando",
                    payload_entrada=payload_log_execucao,
                    id_operacao=id_operacao,
                    nome_operacao=nome_operacao_execucao,
                    observacao="Execucao solicitada pelo aplicativo desktop.",
                )
            except pyodbc.Error:
                pass

            legacy_app.iniciar_execucao_automacao_operacao(
                email,
                senha,
                relatorios_execucao,
                log_execucao_id=log_execucao_id,
                modo_execucao="parceiros",
            )
            return (
                f"Automação iniciada para a operação {id_operacao} "
                f"com {len(relatorios_execucao)} relatório(s)."
            )

        return self._run(_execute, path="/desktop/executar-operacao", method="POST")

    def get_profile(self) -> dict[str, Any]:
        self._require_login()
        return dict(self.current_user)

    def change_password(self, senha_atual: str, nova_senha: str, confirmar_senha: str) -> str:
        self._require_login()
        if not all([senha_atual, nova_senha, confirmar_senha]):
            raise DesktopAppError("Preencha senha atual, nova senha e confirmação.")
        if nova_senha != confirmar_senha:
            raise DesktopAppError("A confirmação da nova senha precisa ser igual.")

        def _change_password() -> str:
            usuario = legacy_app.buscar_usuario_por_login(self.current_user["login"])
            if not usuario or not check_password_hash(usuario.Senha, senha_atual):
                raise DesktopAppError("A senha atual informada está incorreta.")
            legacy_app.atualizar_propria_senha(self.current_user["id"], nova_senha)
            return "Sua senha foi atualizada com sucesso."

        return self._run(_change_password, path="/desktop/minha-senha", method="POST")

    def list_users(self, filtro_busca: str = "", filtro_status: str = "ativos") -> list[dict[str, Any]]:
        self._require_access(legacy_app.ACESSO_ADMIN)
        return self._run(legacy_app.listar_usuarios, filtro_busca, filtro_status, path="/desktop/usuarios")

    def create_user(self, payload: dict[str, Any]) -> str:
        self._require_access(legacy_app.ACESSO_ADMIN)

        login_usuario = str(payload.get("login", "")).strip()
        senha = str(payload.get("senha", ""))
        confirmar_senha = str(payload.get("confirmar_senha", ""))
        email = str(payload.get("email", "")).strip()
        area = str(payload.get("area", "")).strip()
        raw_id_acesso = str(payload.get("id_acesso", "")).strip()

        if not all([email, login_usuario, senha, confirmar_senha, area, raw_id_acesso]):
            raise DesktopAppError("Preencha todos os campos obrigatorios do cadastro de usuario.")
        if senha != confirmar_senha:
            raise DesktopAppError("A confirmacao de senha precisa ser igual a senha informada.")

        try:
            id_acesso = int(raw_id_acesso)
        except ValueError as exc:
            raise DesktopAppError("Selecione um nivel de acesso valido.") from exc

        if id_acesso not in {legacy_app.ACESSO_ADMIN, legacy_app.ACESSO_OPERACAO, legacy_app.ACESSO_EXECUCAO}:
            raise DesktopAppError("Selecione um nivel de acesso valido.")

        def _create() -> str:
            criado = legacy_app.criar_usuario(login_usuario, senha, email, area, id_acesso)
            if not criado:
                raise DesktopAppError("Ja existe um usuario com este login ou email.")
            return "Usuario cadastrado com sucesso."

        return self._run(_create, path="/desktop/usuarios/criar", method="POST")

    def update_user(self, id_login: int, payload: dict[str, Any]) -> str:
        self._require_access(legacy_app.ACESSO_ADMIN)

        email = str(payload.get("email", "")).strip()
        area = str(payload.get("area", "")).strip()
        raw_id_acesso = str(payload.get("id_acesso", "")).strip()
        nova_senha = str(payload.get("nova_senha", ""))
        confirmar_senha = str(payload.get("confirmar_senha", ""))

        if not all([email, area, raw_id_acesso]):
            raise DesktopAppError("Preencha email, area e nivel de acesso para editar o usuario.")
        if nova_senha or confirmar_senha:
            if nova_senha != confirmar_senha:
                raise DesktopAppError("A confirmacao de senha precisa ser igual a senha informada.")

        try:
            id_acesso = int(raw_id_acesso)
        except ValueError as exc:
            raise DesktopAppError("Selecione um nivel de acesso valido.") from exc

        if id_acesso not in {legacy_app.ACESSO_ADMIN, legacy_app.ACESSO_OPERACAO, legacy_app.ACESSO_EXECUCAO}:
            raise DesktopAppError("Selecione um nivel de acesso valido.")

        def _update() -> str:
            atualizado = legacy_app.atualizar_usuario(id_login, email, area, id_acesso, nova_senha)
            if not atualizado:
                raise DesktopAppError("Ja existe outro usuario com este email.")
            return "Usuario atualizado com sucesso."

        return self._run(_update, path=f"/desktop/usuarios/{id_login}/editar", method="POST")

    def deactivate_user(self, id_login: int) -> str:
        self._require_access(legacy_app.ACESSO_ADMIN)
        if self.current_user and self.current_user["id"] == id_login:
            raise DesktopAppError("Nao e permitido inativar o usuario que esta logado.")

        def _deactivate() -> str:
            legacy_app.inativar_usuario(id_login)
            return "Usuario inativado com sucesso."

        return self._run(_deactivate, path=f"/desktop/usuarios/{id_login}/inativar", method="POST")

    def list_logs(self, aba: str = "operacao", filtros: dict[str, str] | None = None) -> list[dict[str, Any]]:
        self._require_access(legacy_app.ACESSO_ADMIN, legacy_app.ACESSO_OPERACAO)
        filtros = filtros or {}
        if aba == "adm":
            return self._run(legacy_app.listar_logs_acesso, filtros, path="/desktop/logs")
        return self._run(legacy_app.listar_logs_execucao, filtros, path="/desktop/logs")

    def list_operacoes(self, filtro_nome: str = "") -> list[dict[str, Any]]:
        self._require_access(legacy_app.ACESSO_ADMIN, legacy_app.ACESSO_OPERACAO)
        return self._run(legacy_app.listar_operacoes, filtro_nome, path="/desktop/operacoes")

    def create_operation(self, nome_operacao: str) -> str:
        self._require_access(legacy_app.ACESSO_ADMIN, legacy_app.ACESSO_OPERACAO)
        nome_operacao = str(nome_operacao or "").strip()
        if not nome_operacao:
            raise DesktopAppError("Informe o nome da operacao antes de salvar.")

        def _create() -> str:
            novo_id = legacy_app.criar_operacao(nome_operacao)
            return f"Operacao criada com sucesso. Codigo gerado: {novo_id}."

        return self._run(_create, path="/desktop/operacoes/criar", method="POST")

    def update_operation(self, operacao_id: int, nome_operacao: str) -> str:
        self._require_access(legacy_app.ACESSO_ADMIN, legacy_app.ACESSO_OPERACAO)
        nome_operacao = str(nome_operacao or "").strip()
        if not nome_operacao:
            raise DesktopAppError("Informe o nome da operacao para editar.")

        def _update() -> str:
            if not legacy_app.usuario_pode_acessar_operacao(operacao_id):
                raise DesktopPermissionError("Voce nao possui permissao para editar esta operacao.")
            legacy_app.atualizar_operacao(operacao_id, nome_operacao)
            return "Operacao atualizada com sucesso."

        return self._run(_update, path=f"/desktop/operacoes/{operacao_id}/editar", method="POST")

    def deactivate_operation(self, operacao_id: int) -> str:
        self._require_access(legacy_app.ACESSO_ADMIN, legacy_app.ACESSO_OPERACAO)

        def _deactivate() -> str:
            if not legacy_app.usuario_pode_acessar_operacao(operacao_id):
                raise DesktopPermissionError("Voce nao possui permissao para inativar esta operacao.")
            legacy_app.inativar_operacao(operacao_id)
            return "Operacao inativada com sucesso."

        return self._run(_deactivate, path=f"/desktop/operacoes/{operacao_id}/inativar", method="POST")

    def get_operation_reports_data(self, operacao_id: int) -> dict[str, Any]:
        self._require_access(legacy_app.ACESSO_ADMIN, legacy_app.ACESSO_OPERACAO)

        def _load() -> dict[str, Any]:
            if not legacy_app.usuario_pode_acessar_operacao(operacao_id):
                raise DesktopPermissionError("Voce nao possui permissao para acessar esta operacao.")

            relatorios_operacao = legacy_app.listar_relatorios_operacao(operacao_id)
            for relatorio in relatorios_operacao:
                relatorio["filtros"] = legacy_app.listar_filtros_operacao_relatorio(
                    operacao_id,
                    relatorio["id_relatorio"],
                )

            return {
                "relatorios_disponiveis": legacy_app.listar_relatorios_disponiveis(),
                "relatorios_operacao": relatorios_operacao,
            }

        return self._run(_load, path=f"/desktop/operacoes/{operacao_id}/relatorios")

    def add_report_to_operation(self, operacao_id: int, id_relatorio: int) -> str:
        self._require_access(legacy_app.ACESSO_ADMIN, legacy_app.ACESSO_OPERACAO)

        def _add() -> str:
            if not legacy_app.usuario_pode_acessar_operacao(operacao_id):
                raise DesktopPermissionError("Voce nao possui permissao para alterar esta operacao.")
            incluido = legacy_app.adicionar_relatorio_operacao(operacao_id, id_relatorio)
            if not incluido:
                raise DesktopAppError("Este relatorio ja esta vinculado na operacao.")
            return "Relatorio vinculado com sucesso."

        return self._run(_add, path=f"/desktop/operacoes/{operacao_id}/relatorios", method="POST")

    def remove_report_from_operation(self, operacao_id: int, id_relatorio: int) -> str:
        self._require_access(legacy_app.ACESSO_ADMIN, legacy_app.ACESSO_OPERACAO)

        def _remove() -> str:
            if not legacy_app.usuario_pode_acessar_operacao(operacao_id):
                raise DesktopPermissionError("Voce nao possui permissao para alterar esta operacao.")
            removido = legacy_app.remover_relatorio_operacao(operacao_id, id_relatorio)
            if not removido:
                raise DesktopAppError("Este relatorio nao esta mais vinculado na operacao.")
            return "Relatorio desvinculado com sucesso."

        return self._run(_remove, path=f"/desktop/operacoes/{operacao_id}/relatorios/remover", method="POST")

    def update_operation_report_filters(self, operacao_id: int, id_relatorio: int, filters: list[tuple[int, str]]) -> str:
        self._require_access(legacy_app.ACESSO_ADMIN, legacy_app.ACESSO_OPERACAO)

        def _update() -> str:
            if not legacy_app.usuario_pode_acessar_operacao(operacao_id):
                raise DesktopPermissionError("Voce nao possui permissao para alterar esta operacao.")
            legacy_app.atualizar_valores_filtros_operacao(operacao_id, id_relatorio, filters)
            return "Valores dos filtros atualizados com sucesso."

        return self._run(_update, path=f"/desktop/operacoes/{operacao_id}/filtros", method="POST")
