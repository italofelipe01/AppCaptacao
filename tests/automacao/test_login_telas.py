"""Login no Sienge percorrendo as telas mapeadas no Sienge, Sienge ID e Microsoft.

O duble do navegador reproduz o que o Selenium enxerga em cada tela, inclusive
os campos ocultos da Microsoft (senha oculta na tela de e-mail e vice-versa).
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

from app_captacao.automacao import erros, login

EMAIL = "usuario@empresa.com.br"
SENHA = "s3nha-de-teste"
HOST = urlsplit(login.LOGIN_URL).hostname
URL_SIENGE = f"https://{HOST}/sienge/"
URL_SIENGE_INDEX = f"https://{HOST}/sienge/index.jsp"
URL_HOME = f"https://{HOST}/sienge/8/index.html"
URL_SIENGE_ID = "https://v-login.sienge.com.br/"
URL_MICROSOFT = "https://login.microsoftonline.com/organizations/oauth2/v2.0/authorize"


class Relogio:
    """Substitui o modulo time do login: sleep avanca o tempo e dispara eventos agendados."""

    def __init__(self):
        self.agora = 1000.0
        self.eventos = []

    def time(self):
        return self.agora

    def sleep(self, segundos):
        self.agora += segundos
        for evento in [e for e in self.eventos if e[0] <= self.agora]:
            self.eventos.remove(evento)
            evento[1]()

    def depois(self, segundos, acao):
        self.eventos.append((self.agora + segundos, acao))


class Elemento:
    def __init__(self, navegador, nome, texto="", atributos=None, visivel=True, ao_clicar=None):
        self.navegador = navegador
        self.nome = nome
        self.text = texto
        self.atributos = dict(atributos or {})
        self.valor = self.atributos.pop("value", "")
        self.visivel = visivel
        self.ao_clicar = ao_clicar

    def is_displayed(self):
        return self.visivel

    def get_attribute(self, nome):
        return self.valor if nome == "value" else self.atributos.get(nome)

    def click(self):
        self.navegador.cliques.append(self.nome)
        if self.ao_clicar:
            self.ao_clicar()

    def clear(self):
        self.valor = ""

    def send_keys(self, *teclas):
        texto = "".join(teclas)
        self.valor += texto
        self.navegador.digitado.append((self.nome, texto))


class Navegador:
    def __init__(self, relogio, inicial):
        self.relogio = relogio
        self.inicial = inicial
        self.atual = None
        self.telas = {}
        self.cliques = []
        self.digitado = []
        self.window_handles = ["janela"]
        self.current_window_handle = "janela"
        self.switch_to = SimpleNamespace(window=lambda handle: None)

    @property
    def current_url(self):
        return self.telas[self.atual]["url"]

    def tela(self, nome, url, elementos):
        self.telas[nome] = {"url": url, "elementos": elementos}

    def ir(self, nome):
        self.atual = nome

    def get(self, url):
        self.ir(self.inicial)

    def find_elements(self, by, valor):
        return list(self.telas[self.atual]["elementos"].get((by, valor), []))

    def execute_script(self, script, *args):
        if "readyState" in script:
            return "complete"
        if "click" in script:
            args[0].click()
        return None

    # Telas, como capturadas no Sienge da EBM (out/2026).
    def sienge_entrar(self, proxima):
        self.tela(
            "sienge_entrar",
            URL_SIENGE,
            {login._SIENGE_ENTRAR: [Elemento(self, "entrar_sienge_id", ao_clicar=lambda: self.ir(proxima))]},
        )

    def sienge_ja_conectado(self, proxima):
        self.tela(
            "ja_conectado",
            URL_SIENGE_INDEX,
            {login._SIENGE_PROSSEGUIR: [Elemento(self, "prosseguir", ao_clicar=lambda: self.ir(proxima))]},
        )

    def sienge_logado(self):
        self.tela("logado", URL_HOME, {})

    def sienge_id_email(self, proxima):
        self.tela(
            "sid_email",
            URL_SIENGE_ID,
            {
                login._SID_PAGINA: [Elemento(self, "pagina_sienge_id")],
                login._SID_EMAIL: [Elemento(self, "sid_email")],
                login._SID_CONTINUAR: [Elemento(self, "sid_continuar", ao_clicar=lambda: self.ir(proxima))],
            },
        )

    def sienge_id_escolher_conta(self, usuario_atual=None, lembrados=(), proxima="", outra_conta=""):
        elementos = {
            login._SID_PAGINA: [Elemento(self, "pagina_sienge_id")],
            login._SID_ESCOLHER_CONTA: [Elemento(self, "lista_sienge_id")],
            login._SID_USAR_OUTRA_CONTA: [
                Elemento(self, "sid_usar_outra_conta", ao_clicar=lambda: self.ir(outra_conta))
            ],
        }
        if usuario_atual:
            elementos[login._SID_USUARIO_ATUAL] = [
                Elemento(self, "sid_usuario_atual", texto=f"{usuario_atual} Conectado", ao_clicar=lambda: self.ir(proxima))
            ]
        elementos[login._SID_CONTA_LEMBRADA] = [
            Elemento(self, f"sid_lembrado:{email}", texto=email, ao_clicar=lambda: self.ir(proxima))
            for email in lembrados
        ]
        self.tela("sid_escolher_conta", URL_SIENGE_ID, elementos)

    def microsoft_escolher_conta(self, contas, proxima, outra_conta=""):
        self.tela(
            "ms_contas",
            URL_MICROSOFT,
            {
                login._MS_CONTAS: [Elemento(self, "lista_microsoft")],
                login._MS_CONTA: [
                    Elemento(self, f"ms_conta:{email}", atributos={"data-test-id": email}, ao_clicar=lambda: self.ir(proxima))
                    for email in contas
                ],
                login._MS_OUTRA_CONTA: [Elemento(self, "ms_outra_conta", ao_clicar=lambda: self.ir(outra_conta))],
                login._MS_AVANCAR: [Elemento(self, "ms_avancar_oculto", visivel=False)],
            },
        )

    def microsoft_email(self, proxima):
        self.tela(
            "ms_email",
            URL_MICROSOFT,
            {
                login._MS_EMAIL: [Elemento(self, "ms_email")],
                login._MS_SENHA: [Elemento(self, "ms_senha_oculta", visivel=False)],
                login._MS_AVANCAR: [Elemento(self, "ms_avancar", ao_clicar=lambda: self.ir(proxima))],
            },
        )

    def microsoft_senha(self, ao_entrar):
        self.tela(
            "ms_senha",
            URL_MICROSOFT,
            {
                login._MS_EMAIL: [Elemento(self, "ms_email_oculto", atributos={"value": EMAIL}, visivel=False)],
                login._MS_SENHA: [Elemento(self, "ms_senha")],
                login._MS_AVANCAR: [Elemento(self, "ms_entrar", ao_clicar=ao_entrar)],
                login._MS_NAO: [Elemento(self, "ms_seta_voltar")],
            },
        )

    def microsoft_erro_senha(self):
        self.tela(
            "ms_erro",
            URL_MICROSOFT,
            {
                login._MS_SENHA: [Elemento(self, "ms_senha")],
                login._MS_ERRO: [Elemento(self, "ms_erro", texto="Sua conta ou senha esta incorreta.")],
            },
        )

    def microsoft_mfa(self):
        self.tela(
            "ms_mfa",
            "https://login.microsoftonline.com/common/login",
            {
                login._MS_MFA: [Elemento(self, "ms_mfa_titulo")],
                login._MS_MFA_NUMERO: [Elemento(self, "ms_mfa_numero", texto="89")],
                login._MS_AVANCAR: [Elemento(self, "ms_avancar_oculto", visivel=False)],
            },
        )

    def microsoft_continuar_conectado(self, proxima):
        self.tela(
            "ms_kmsi",
            "https://login.microsoftonline.com/kmsi",
            {
                login._MS_CONTINUAR_CONECTADO: [Elemento(self, "ms_kmsi_checkbox")],
                login._MS_NAO: [Elemento(self, "ms_nao", ao_clicar=lambda: self.ir(proxima))],
                login._MS_AVANCAR: [Elemento(self, "ms_sim")],
            },
        )


class LoginPorTelasTests(unittest.TestCase):
    def setUp(self):
        self.relogio = Relogio()
        patcher = patch.object(login, "time", self.relogio)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _logar(self, navegador, email=EMAIL, senha=SENHA):
        login._fazer_login_automatico(navegador, email, senha)

    def test_windows_ligado_ao_entra_usa_a_conta_da_lista_sem_digitar_senha(self):
        nav = Navegador(self.relogio, "sienge_entrar")
        nav.sienge_entrar("sid_email")
        nav.sienge_id_email("ms_contas")
        nav.microsoft_escolher_conta(["outra.pessoa@empresa.com.br", EMAIL.upper()], "logado", outra_conta="ms_email")
        nav.sienge_logado()

        self._logar(nav)

        self.assertEqual(nav.atual, "logado")
        self.assertEqual(nav.digitado, [("sid_email", EMAIL)])
        self.assertIn(f"ms_conta:{EMAIL.upper()}", nav.cliques)
        self.assertNotIn("ms_outra_conta", nav.cliques)

    def test_conta_lembrada_no_sienge_id_e_sessao_aberta_em_outro_navegador(self):
        nav = Navegador(self.relogio, "sienge_entrar")
        nav.sienge_entrar("sid_escolher_conta")
        nav.sienge_id_escolher_conta(usuario_atual=EMAIL, proxima="ja_conectado", outra_conta="sid_email")
        nav.sienge_ja_conectado("logado")
        nav.sienge_logado()

        self._logar(nav)

        self.assertEqual(nav.atual, "logado")
        self.assertEqual(nav.cliques, ["entrar_sienge_id", "sid_usuario_atual", "prosseguir"])
        self.assertEqual(nav.digitado, [])

    def test_email_lembrado_sem_sessao_no_sienge_id_escolhe_o_item_da_lista(self):
        nav = Navegador(self.relogio, "sienge_entrar")
        nav.sienge_entrar("sid_escolher_conta")
        nav.sienge_id_escolher_conta(
            lembrados=["outra.pessoa@empresa.com.br", EMAIL], proxima="ms_contas", outra_conta="sid_email"
        )
        nav.microsoft_escolher_conta([EMAIL], "logado")
        nav.sienge_logado()

        self._logar(nav)

        self.assertEqual(nav.atual, "logado")
        self.assertIn(f"sid_lembrado:{EMAIL}", nav.cliques)
        self.assertNotIn("sid_usar_outra_conta", nav.cliques)

    def test_maquina_sem_sso_digita_email_e_senha_e_espera_a_aprovacao_do_mfa(self):
        nav = Navegador(self.relogio, "sienge_entrar")
        nav.sienge_entrar("sid_email")
        nav.sienge_id_email("ms_email")
        nav.microsoft_email("ms_senha")

        def aprovar_mfa_depois_de_20s():
            nav.ir("ms_mfa")
            self.relogio.depois(20, lambda: nav.ir("ms_kmsi"))

        nav.microsoft_senha(aprovar_mfa_depois_de_20s)
        nav.microsoft_mfa()
        nav.microsoft_continuar_conectado("ja_conectado")
        nav.sienge_ja_conectado("logado")
        nav.sienge_logado()

        self._logar(nav)

        self.assertEqual(nav.atual, "logado")
        self.assertEqual(nav.digitado, [("sid_email", EMAIL), ("ms_email", EMAIL), ("ms_senha", SENHA)])
        # A seta "voltar" da tela de senha tem o mesmo id do "Nao" do continuar conectado.
        self.assertNotIn("ms_seta_voltar", nav.cliques)
        self.assertIn("ms_nao", nav.cliques)
        self.assertNotIn("ms_sim", nav.cliques)

    def test_conta_de_outra_pessoa_nas_listas_leva_a_usar_outra_conta(self):
        nav = Navegador(self.relogio, "sienge_entrar")
        nav.sienge_entrar("sid_escolher_conta")
        nav.sienge_id_escolher_conta(
            usuario_atual="outra.pessoa@empresa.com.br", proxima="ms_contas", outra_conta="sid_email"
        )
        nav.sienge_id_email("ms_contas")
        nav.microsoft_escolher_conta(["outra.pessoa@empresa.com.br"], "logado", outra_conta="ms_email")
        nav.microsoft_email("ms_senha")
        nav.microsoft_senha(lambda: nav.ir("logado"))
        nav.sienge_logado()

        self._logar(nav)

        self.assertEqual(nav.atual, "logado")
        self.assertIn("sid_usar_outra_conta", nav.cliques)
        self.assertNotIn("sid_usuario_atual", nav.cliques)
        self.assertIn("ms_outra_conta", nav.cliques)
        self.assertNotIn("ms_conta:outra.pessoa@empresa.com.br", nav.cliques)

    def test_senha_recusada_interrompe_sem_enviar_a_senha_de_novo(self):
        nav = Navegador(self.relogio, "ms_senha")
        nav.microsoft_senha(lambda: nav.ir("ms_erro"))
        nav.microsoft_erro_senha()

        with self.assertRaisesRegex(erros.InteractiveAuthenticationRequired, "recusou o login: Sua conta ou senha"):
            self._logar(nav)

        self.assertEqual(nav.digitado, [("ms_senha", SENHA)])

    def test_senha_sem_resposta_nao_e_reenviada(self):
        nav = Navegador(self.relogio, "ms_senha")
        nav.microsoft_senha(lambda: None)

        with self.assertRaisesRegex(erros.InteractiveAuthenticationRequired, "microsoft_senha"):
            self._logar(nav)

        self.assertEqual(nav.digitado, [("ms_senha", SENHA)])

    def test_mfa_nao_aprovado_desiste_depois_do_prazo_do_token(self):
        nav = Navegador(self.relogio, "ms_mfa")
        nav.microsoft_mfa()
        inicio = self.relogio.agora

        with patch.object(login, "MICROSOFT_MFA_WAIT", 60), self.assertRaisesRegex(
            erros.InteractiveAuthenticationRequired, "microsoft_mfa"
        ):
            self._logar(nav)

        self.assertGreaterEqual(self.relogio.agora - inicio, 60)
        self.assertEqual(nav.cliques, [])

    def test_sessao_ja_ativa_conclui_sem_passar_pelo_login(self):
        nav = Navegador(self.relogio, "logado")
        nav.sienge_logado()

        self._logar(nav)

        self.assertEqual(nav.cliques, [])
        self.assertEqual(nav.digitado, [])


class FalhaDoLoginAutomaticoTests(unittest.TestCase):
    def test_motivo_da_falha_chega_na_mensagem_final(self):
        with patch.object(
            login,
            "_fazer_login_automatico",
            side_effect=erros.InteractiveAuthenticationRequired("A Microsoft recusou o login: senha incorreta."),
        ), patch.object(login, "_aguardar_autenticacao_interativa", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "nao foi concluida: A Microsoft recusou o login: senha incorreta\\."):
                login.fazer_login(object(), None, EMAIL, SENHA)


if __name__ == "__main__":
    unittest.main()
