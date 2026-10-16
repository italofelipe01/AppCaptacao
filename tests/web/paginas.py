"""Telas renderizadas com os dubles de banco, para os testes de estrutura e de texto do frontend."""

from html.parser import HTMLParser
from unittest.mock import patch

from app_captacao.app import app
from app_captacao.catalogo import operacoes, relatorios
from app_captacao.core.persistence import logs as logs_repo
from app_captacao.core.persistence import usuarios
from app_captacao.execucao import jobs

ADMIN = {"id": 10, "login": "admin", "email": "a@example.com", "area": "ti", "access_id": 1, "ativo": 1, "data_criacao": None}


class Elementos(HTMLParser):
    """Tags na ordem do documento e o texto visivel. O conteudo de <script> nao vira tag nem texto."""

    ATRIBUTOS_VISIVEIS = ("placeholder", "title", "aria-label", "alt")

    def __init__(self, html):
        super().__init__()
        self.elementos: list[tuple[str, dict[str, str]]] = []
        self.textos: list[str] = []
        self._dentro_de_script = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        atributos = {nome: valor or "" for nome, valor in attrs}
        self.elementos.append((tag, atributos))
        if tag in ("script", "style"):
            self._dentro_de_script += 1
        self.textos += [atributos[nome] for nome in self.ATRIBUTOS_VISIVEIS if atributos.get(nome)]

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._dentro_de_script -= 1

    def handle_data(self, data):
        if not self._dentro_de_script and data.strip():
            self.textos.append(data.strip())

    def com(self, **filtro):
        return [attrs for _, attrs in self.elementos if all(attrs.get(k) == v for k, v in filtro.items())]

    def ids(self):
        return {attrs["id"] for _, attrs in self.elementos if attrs.get("id")}


def obter(client, rota, *, logado=True, flashes=None, job=None, resultado=None, usuarios_lista=(), logs_adm=(), logs_operacao=()):
    """GET da rota com o administrador na sessao (ou sem sessao) e o banco simulado."""
    app.config.update(TESTING=True, SECRET_KEY="test")
    with client.session_transaction() as session:
        session.clear()
        if logado:
            session["user_id"] = ADMIN["id"]
            session["user_login"] = ADMIN["login"]
            session["user_access_id"] = ADMIN["access_id"]
        if flashes:
            session["_flashes"] = flashes
    with patch.object(usuarios, "load_user_by_id", return_value=ADMIN), patch.object(
        usuarios, "load_usuarios", return_value=list(usuarios_lista)
    ), patch.object(operacoes, "load_operacoes", return_value=[]), patch.object(
        operacoes, "load_operation_report_summaries", return_value={}
    ), patch.object(relatorios, "load_relatorios_disponiveis", return_value=[]), patch.object(
        logs_repo, "load_logs_configuracao", return_value=list(logs_adm)
    ), patch.object(logs_repo, "load_logs_operacao", return_value=list(logs_operacao)), patch.object(
        jobs, "get_current_execution_job", return_value=job
    ), patch.object(jobs, "get_last_execution_result_for_current_session", return_value=resultado):
        resposta = client.get(rota)
    if resposta.status_code != 200:
        raise AssertionError(f"{rota}: status {resposta.status_code}")
    return resposta.get_data(as_text=True)
