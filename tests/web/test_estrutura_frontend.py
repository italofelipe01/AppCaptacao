"""Estrutura e acessibilidade das telas (docs/specs/frontend-estrutura-acessibilidade.md).

Renderiza as telas com os dubles e confere o HTML entregue ao navegador. Foco, Tab e Esc dos
modais dependem do navegador e foram conferidos no Edge (ver a spec).
"""

import unittest
from pathlib import Path

from app_captacao.app import app
from tests.web.paginas import Elementos, obter

MODAL_JS = Path(__file__).resolve().parents[2] / "project" / "static" / "js" / "modal.js"
JOB_EM_ANDAMENTO = {
    "estado": "em_execucao",
    "resumo": "Executando 1 de 2.",
    "itens": [{"relatorio_nome": "Unidades", "operacao_nome": "", "estado": "em_execucao", "mensagem": ""}],
}
RESULTADO_ANTERIOR = {
    "resumo": "1 relatório(s) baixado(s).",
    "quantidade_baixados": 1,
    "quantidade_nao_baixados": 0,
    "itens": [{"relatorio_nome": "Unidades", "operacao_nome": "", "estado": "baixado", "mensagem": "ok", "etapa": "", "caminho_final": ""}],
}
CAMPOS_SEM_ROTULO_PROPRIO = {"hidden", "submit", "button"}


class EstruturaFrontendTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _get(self, rota, **kwargs):
        return obter(self.client, rota, **kwargs)

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
            pagina = Elementos(self._get(rota))
            obtido = {id_campo: (pagina.com(id=id_campo) or [{}])[0].get("autocomplete") for id_campo in campos}
            self.assertEqual(obtido, campos, rota)

    def test_todo_campo_visivel_tem_rotulo_ligado(self):
        rotas = ["/main", "/usuarios", "/acompanhamento", "/perfil", "/logs?aba=operacao", "/logs?aba=adm"]
        paginas = {rota: self._get(rota) for rota in rotas}
        paginas["/"] = self._get("/", logado=False)
        for rota, html in paginas.items():
            pagina = Elementos(html)
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
        html = self._get("/main", job=JOB_EM_ANDAMENTO, resultado=RESULTADO_ANTERIOR, flashes=[("error", "Destino inválido")])
        blocos = ("mensagens-execucao", "execucao-andamento", "resultado-execucao", "form-execucao")
        posicoes = [html.find(f'id="{id_bloco}"') for id_bloco in blocos]
        self.assertNotIn(-1, posicoes)
        self.assertEqual(posicoes, sorted(posicoes))
        andamento = Elementos(html).com(id="execucao-andamento")[0]
        self.assertNotIn("hidden", andamento["class"].split())

    def test_so_o_resumo_do_andamento_e_anunciado(self):
        # O painel e refeito a cada 1,2 s: com aria-live nele o leitor de tela relia a lista inteira.
        pagina = Elementos(self._get("/main", job=JOB_EM_ANDAMENTO))
        vivos = [attrs.get("id") for _, attrs in pagina.elementos if "aria-live" in attrs]
        self.assertEqual(vivos, ["execucao-resumo"])

    def test_modais_tem_titulo_e_usam_o_script_unico(self):
        modal_js = MODAL_JS.read_text(encoding="utf-8")
        self.assertIn("function abrirModal(", modal_js)
        self.assertIn("function fecharModal(", modal_js)
        for rota in ("/usuarios", "/acompanhamento"):
            html = self._get(rota)
            pagina = Elementos(html)
            dialogos = pagina.com(role="dialog")
            self.assertTrue(dialogos, rota)
            for dialogo in dialogos:
                self.assertIn(dialogo.get("aria-labelledby"), pagina.ids(), f"{rota}: {dialogo.get('id')}")
            self.assertTrue(any("js/modal.js" in attrs.get("src", "") for attrs in pagina.com()), rota)
            # Uma copia local redefiniria as funcoes e perderia o foco, o Tab e a confirmacao do Esc.
            self.assertNotRegex(html, r"function (abrirModal|fecharModal)\(", rota)

    def test_pagina_ativa_marcada_no_menu(self):
        for rota, href in (("/logs", "/logs"), ("/main", "/main")):
            ativos = [attrs.get("href") for _, attrs in Elementos(self._get(rota)).elementos if attrs.get("aria-current") == "page"]
            self.assertEqual(ativos, [href], rota)

    def test_mensagens_de_erro_e_sucesso_sao_anunciadas(self):
        flashes = [("error", "Falha de teste"), ("success", "Feito de teste")]
        for rota, logado in (("/", False), ("/main", True), ("/usuarios", True), ("/acompanhamento", True), ("/perfil", True)):
            html = self._get(rota, logado=logado, flashes=flashes)
            self.assertRegex(html, r'role="alert"[^>]*>\s*Falha de teste', rota)
            self.assertRegex(html, r'role="status"[^>]*>\s*Feito de teste', rota)


if __name__ == "__main__":
    unittest.main()
