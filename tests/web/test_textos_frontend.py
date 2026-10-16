"""Textos das telas (docs/specs/frontend-textos.md): acentos, nome do app, valores pelo nome.

O texto visivel e o das tags e dos atributos que o navegador mostra (placeholder, title,
aria-label, alt). `id`, `name`, `value` e codigo ficam de fora: sao contrato com o backend.
"""

import re
import unittest
from unittest.mock import patch

from app_captacao.app import app
from app_captacao.core.config import settings
from tests.web.paginas import Elementos, obter

SEM_ACENTO = re.compile(
    r"\b(execucao|execucoes|relatorios?|operacao|operacoes|usuarios?|acoes|acao|codigo|nivel|area|criacao|"
    r"edicao|inativacao|historico|configuracao|automacao|responsavel|atualizacao|inicio|periodo|obrigatorios?|"
    r"automatica|numeros?|virgula|padrao|nao|sao|vinculo|catalogo|possivel|diagnostico|tecnico|sequencia|"
    r"invalidos?|disponivel|alteracoes|voce|Edicao)\b",
    re.IGNORECASE,
)
USUARIO = {"id": 4, "login": "ana", "email": "ana@example.com", "area": "captacao", "perfil": "Usuário com cadastro de operação",
           "id_acesso": 2, "ativo": True, "status": "Ativo"}
LOG_ADM = {"usuario": "admin", "evento": "login_falha", "data_evento": "16/10/2026 08:59", "detalhe": "Senha inválida.", "payload_json": ""}
LOG_OPERACAO = {"nome_operacao": "", "tipo_execucao": "relatorio", "nome_relatorio": "Unidades", "status": "sucesso",
                "responsavel": "admin", "atualizacao": "16/10/2026 09:19", "observacao": "", "empresa": [], "empreendimento": [],
                "filtros_resumo": {}, "payload_entrada_json": "", "payload_resultado_json": "", "erro_json": ""}
JOB = {"estado": "em_execucao", "resumo": "Preparando 1 relatório(s).",
       "itens": [{"relatorio_nome": "Unidades", "operacao_nome": "", "estado": "em_execucao", "mensagem": ""}]}
RESULTADO = {"resumo": "0 relatório(s) baixado(s); 1 não baixado(s).", "quantidade_baixados": 0, "quantidade_nao_baixados": 1,
             "itens": [{"relatorio_nome": "Unidades", "operacao_nome": "Fechamento", "estado": "nao_baixado",
                        "mensagem": "Nenhum arquivo novo.", "etapa": "download", "caminho_final": ""}]}


class TextosFrontendTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _telas(self):
        return {
            "/": obter(self.client, "/", logado=False),
            "/main": obter(self.client, "/main", job=JOB, resultado=RESULTADO),
            "/usuarios": obter(self.client, "/usuarios", usuarios_lista=[USUARIO]),
            "/acompanhamento": obter(self.client, "/acompanhamento"),
            "/perfil": obter(self.client, "/perfil"),
            "/logs?aba=operacao": obter(self.client, "/logs?aba=operacao", logs_operacao=[LOG_OPERACAO]),
            "/logs?aba=adm": obter(self.client, "/logs?aba=adm", logs_adm=[LOG_ADM]),
        }

    def test_texto_visivel_das_telas_tem_acentos(self):
        sem_acento = {}
        for rota, html in self._telas().items():
            achados = sorted({m.group(0) for texto in Elementos(html).textos for m in SEM_ACENTO.finditer(texto)})
            if achados:
                sem_acento[rota] = achados
        self.assertEqual(sem_acento, {})

    def test_titulo_da_aba_e_o_nome_do_app_sao_os_mesmos_em_todas_as_telas(self):
        for rota, html in self._telas().items():
            titulo = re.search(r"<title>(.*?)</title>", html, re.S)
            self.assertIsNotNone(titulo, rota)
            assert titulo is not None
            self.assertRegex(titulo.group(1).strip(), r"^\S.* \| AppCaptação$", rota)
            self.assertNotIn("Control Center", html, rota)
            self.assertNotIn("EBM Automacao", html, rota)

    def test_valores_gravados_aparecem_pelo_nome(self):
        telas = self._telas()
        visivel = {rota: " | ".join(Elementos(html).textos) for rota, html in telas.items()}
        self.assertIn("Captação", visivel["/usuarios"])
        self.assertIn("Usuário com cadastro de operação", visivel["/usuarios"])
        self.assertIn("TI", visivel["/perfil"])
        self.assertIn("Falha de login", visivel["/logs?aba=adm"])
        self.assertNotIn("login_falha", visivel["/logs?aba=adm"])
        self.assertIn("Relatório", visivel["/logs?aba=operacao"])
        self.assertIn("Sucesso", visivel["/logs?aba=operacao"])
        for esperado in ("Em execução", "Não baixado", "Download:"):
            self.assertIn(esperado, visivel["/main"])

    def test_textos_que_nao_correspondiam_ao_sistema_sairam(self):
        telas = self._telas()
        # A sessao nunca e restaurada (D6) e o Edge fecha no fim (D17).
        self.assertNotIn("Sessão protegida", telas["/main"])
        self.assertIn("Login a cada execução", telas["/main"])
        # O login e o usuario do AppCaptacao, nao a conta Microsoft.
        self.assertNotIn("conta corporativa", telas["/"])
        # Logs no banco estao desligados; o detalhe tecnico fica no log do computador.
        self.assertIn(r"%LOCALAPPDATA%\AppCaptacao\logs\appcaptacao.log", telas["/main"])

    def test_lista_vazia_de_logs_diz_o_motivo(self):
        with patch.object(settings, "SAVE_LOGS", False):
            desligado = obter(self.client, "/logs?aba=operacao")
            filtrado = obter(self.client, "/logs?aba=operacao&responsavel=ninguem")
        with patch.object(settings, "SAVE_LOGS", True):
            ligado = obter(self.client, "/logs?aba=operacao")
        self.assertIn("A gravação de logs no banco está desligada", desligado)
        self.assertIn("Nenhum registro com estes filtros", filtrado)
        self.assertNotIn("está desligada", filtrado)
        self.assertIn("Ainda não há registros.", ligado)
        for html in (desligado, filtrado, ligado):
            self.assertNotIn("assim que os registros do banco forem conectados", html)


if __name__ == "__main__":
    unittest.main()
