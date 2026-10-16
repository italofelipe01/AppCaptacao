"""Estrutura e acessibilidade das telas (docs/specs/frontend-estrutura-acessibilidade.md).

Renderiza as telas com os dubles e confere o HTML entregue ao navegador. Foco, Tab e Esc dos
modais dependem do navegador e foram conferidos no Edge (ver a spec).
"""

import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from app_captacao.app import app
from app_captacao.catalogo import operacoes, relatorios
from app_captacao.core.persistence import logs as logs_repo
from app_captacao.core.persistence import usuarios
from app_captacao.execucao import jobs

MODAL_JS = Path(__file__).resolve().parents[2] / "project" / "static" / "js" / "modal.js"
ADMIN = {"id": 10, "login": "admin", "email": "a@example.com", "area": "ti", "access_id": 1, "ativo": 1, "data_criacao": None}
JOB_EM_ANDAMENTO = {
    "estado": "em_execucao",
    "resumo": "Executando 1 de 2.",
    "itens": [{"relatorio_nome": "Unidades", "operacao_nome": "", "estado": "em_execucao", "mensagem": ""}],
}
RESULTADO_ANTERIOR = {
    "resumo": "1 relatorio(s) baixado(s).",
    "quantidade_baixados": 1,
    "quantidade_nao_baixados": 0,
    "itens": [{"relatorio_nome": "Unidades", "operacao_nome": "", "estado": "baixado", "mensagem": "ok", "etapa": "", "caminho_final": ""}],
}
CAMPOS_SEM_ROTULO_PROPRIO = {"hidden", "submit", "button"}


class _Elementos(HTMLParser):
    """Tags na ordem do documento. O conteudo de <script> nao vira tag (HTMLParser o trata como texto)."""

    def __init__(self, html):
        super().__init__()
        self.elementos: list[tuple[str, dict[str, str]]] = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elementos.append((tag, {nome: valor or "" for nome, valor in attrs}))

    def com(self, **filtro):
        return [attrs for _, attrs in self.elementos if all(attrs.get(k) == v for k, v in filtro.items())]

    def ids(self):
        return {attrs["id"] for _, attrs in self.elementos if attrs.get("id")}


class EstruturaFrontendTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, SECRET_KEY="test")
        self.client = app.test_client()

    def _get(self, rota, *, logado=True, flashes=None, job=None, resultado=None):
        with self.client.session_transaction() as session:
            session.clear()
            if logado:
                session["user_id"] = ADMIN["id"]
                session["user_login"] = ADMIN["login"]
                session["user_access_id"] = ADMIN["access_id"]
            if flashes:
                session["_flashes"] = flashes
        with patch.object(usuarios, "load_user_by_id", return_value=ADMIN), patch.object(
            usuarios, "load_usuarios", return_value=[]
        ), patch.object(operacoes, "load_operacoes", return_value=[]), patch.object(
            operacoes, "load_operation_report_summaries", return_value={}
        ), patch.object(relatorios, "load_relatorios_disponiveis", return_value=[]), patch.object(
            logs_repo, "load_logs_configuracao", return_value=[]
        ), patch.object(logs_repo, "load_logs_operacao", return_value=[]), patch.object(
            jobs, "get_current_execution_job", return_value=job
        ), patch.object(jobs, "get_last_execution_result_for_current_session", return_value=resultado):
            resposta = self.client.get(rota)
        self.assertEqual(resposta.status_code, 200, rota)
        return resposta.get_data(as_text=True)

    def test_senhas_tem_o_autocomplete_certo(self):
        # Sem new-password o Edge preenche a senha do administrador logado no usuario novo/editado.
        esperado = {
            "/usuarios": {
                "criar-senha": "new-password",
                "criar-confirmar-senha": "new-password",
                "editar-usuario-senha": "new-password",
                "editar-usuario-confirmar-senha": "new-password",
                "criar-login": "off",
            },
            "/perfil": {"senha_atual": "current-password", "nova_senha": "new-password", "confirmar_senha": "new-password"},
        }
        for rota, campos in esperado.items():
            pagina = _Elementos(self._get(rota))
            obtido = {id_campo: (pagina.com(id=id_campo) or [{}])[0].get("autocomplete") for id_campo in campos}
            self.assertEqual(obtido, campos, rota)

    def test_todo_campo_visivel_tem_rotulo_ligado(self):
        rotas = ["/main", "/usuarios", "/acompanhamento", "/perfil", "/logs?aba=operacao", "/logs?aba=adm"]
        paginas = {rota: self._get(rota) for rota in rotas}
        paginas["/"] = self._get("/", logado=False)
        for rota, html in paginas.items():
            pagina = _Elementos(html)
            ids = pagina.ids()
            rotulados = {attrs["for"] for tag, attrs in pagina.elementos if tag == "label" and attrs.get("for")}
            self.assertEqual(rotulados - ids, set(), f"{rota}: label aponta para campo inexistente")
            sem_rotulo = [
                attrs.get("name") or attrs.get("id") or tag
                for tag, attrs in pagina.elementos
                if tag in ("input", "select", "textarea")
                and attrs.get("type", "text") not in CAMPOS_SEM_ROTULO_PROPRIO
                and attrs.get("id") not in rotulados
                and not attrs.get("aria-label")
                and not attrs.get("aria-labelledby")
            ]
            self.assertEqual(sem_rotulo, [], f"{rota}: campo sem rotulo")

    def test_andamento_e_resultado_vem_antes_do_formulario(self):
        # As mensagens vem antes de tudo: depois do resultado, um erro de destino ficaria fora da tela.
        html = self._get("/main", job=JOB_EM_ANDAMENTO, resultado=RESULTADO_ANTERIOR, flashes=[("error", "Destino invalido")])
        blocos = ("mensagens-execucao", "execucao-andamento", "resultado-execucao", "form-execucao")
        posicoes = [html.find(f'id="{id_bloco}"') for id_bloco in blocos]
        self.assertNotIn(-1, posicoes)
        self.assertEqual(posicoes, sorted(posicoes))
        andamento = _Elementos(html).com(id="execucao-andamento")[0]
        self.assertNotIn("hidden", andamento["class"].split())

    def test_so_o_resumo_do_andamento_e_anunciado(self):
        # O painel e refeito a cada 1,2 s: com aria-live nele o leitor de tela relia a lista inteira.
        pagina = _Elementos(self._get("/main", job=JOB_EM_ANDAMENTO))
        vivos = [attrs.get("id") for _, attrs in pagina.elementos if "aria-live" in attrs]
        self.assertEqual(vivos, ["execucao-resumo"])

    def test_modais_tem_titulo_e_usam_o_script_unico(self):
        modal_js = MODAL_JS.read_text(encoding="utf-8")
        self.assertIn("function abrirModal(", modal_js)
        self.assertIn("function fecharModal(", modal_js)
        for rota in ("/usuarios", "/acompanhamento"):
            html = self._get(rota)
            pagina = _Elementos(html)
            dialogos = pagina.com(role="dialog")
            self.assertTrue(dialogos, rota)
            for dialogo in dialogos:
                self.assertIn(dialogo.get("aria-labelledby"), pagina.ids(), f"{rota}: {dialogo.get('id')}")
            self.assertTrue(any("js/modal.js" in attrs.get("src", "") for attrs in pagina.com()), rota)
            # Uma copia local redefiniria as funcoes e perderia o foco, o Tab e a confirmacao do Esc.
            self.assertNotRegex(html, r"function (abrirModal|fecharModal)\(", rota)

    def test_pagina_ativa_marcada_no_menu(self):
        for rota, href in (("/logs", "/logs"), ("/main", "/main")):
            ativos = [attrs.get("href") for _, attrs in _Elementos(self._get(rota)).elementos if attrs.get("aria-current") == "page"]
            self.assertEqual(ativos, [href], rota)

    def test_mensagens_de_erro_e_sucesso_sao_anunciadas(self):
        flashes = [("error", "Falha de teste"), ("success", "Feito de teste")]
        for rota, logado in (("/", False), ("/main", True), ("/usuarios", True), ("/acompanhamento", True), ("/perfil", True)):
            html = self._get(rota, logado=logado, flashes=flashes)
            self.assertRegex(html, r'role="alert"[^>]*>\s*Falha de teste', rota)
            self.assertRegex(html, r'role="status"[^>]*>\s*Feito de teste', rota)


if __name__ == "__main__":
    unittest.main()
