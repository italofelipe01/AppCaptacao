import os
import sys
import types
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app_captacao.core.database import connection
from app_captacao.core.security import auth, sessao_usuario
from app_captacao.inicializacao import dependencias


class ConexaoTests(unittest.TestCase):
    def test_db_database_vazio_nao_usa_db_schema(self):
        with patch.dict(os.environ, {"DB_DATABASE": "", "DB_SCHEMA": "dbo"}):
            self.assertEqual(connection.nome_do_banco(), "")

    def test_db_schema_legado_vale_sem_db_database(self):
        ambiente = {chave: valor for chave, valor in os.environ.items() if chave != "DB_DATABASE"}
        with patch.dict(os.environ, {**ambiente, "DB_SCHEMA": "BancoLegado"}, clear=True):
            self.assertEqual(connection.nome_do_banco(), "BancoLegado")

    def test_senha_com_ponto_e_virgula_e_chave_vai_escapada(self):
        self.assertEqual(connection._valor_odbc("a;b}c"), "{a;b}}c}")


class SenhaTests(unittest.TestCase):
    def test_hash_valido(self):
        self.assertTrue(auth.verify_password("certa", generate_password_hash("certa")))
        self.assertFalse(auth.verify_password("errada", generate_password_hash("certa")))

    def test_hash_corrompido_nao_aceita_o_proprio_texto_do_hash(self):
        corrompido = "scrypt:metodo-invalido$x$y"
        self.assertFalse(auth.verify_password(corrompido, corrompido))

    def test_senha_legada_em_texto_puro(self):
        self.assertTrue(auth.verify_password("legada", "legada"))
        self.assertFalse(auth.verify_password("outra", "legada"))

    def test_sessao_sem_id_nao_autentica(self):
        self.assertIsNone(sessao_usuario.carregar_usuario_da_sessao({"user_login": "ana", "user_access_id": 1}))


class VersaoTests(unittest.TestCase):
    def test_zeros_a_direita_nao_mudam_a_versao(self):
        self.assertTrue(dependencias.versao_atende("3.1", ">=3.1.0"))
        self.assertTrue(dependencias.versao_atende("2.0.0", "==2.0"))
        self.assertFalse(dependencias.versao_atende("3.0.9", ">=3.1"))


class ConfiguradorTests(unittest.TestCase):
    def test_chave_de_sessao_vazia_conta_como_ausente(self):
        falso = types.SimpleNamespace(CTk=object, set_appearance_mode=lambda *_: None, set_default_color_theme=lambda *_: None)
        with patch.dict(sys.modules, {"customtkinter": falso}):
            sys.modules.pop("app_captacao.desktop.config_installer", None)
            from app_captacao.desktop import config_installer
        self.assertEqual(config_installer._valor_env(config_installer.DEFAULT_ENV_TEMPLATE, "FLASK_SECRET_KEY"), "")
        self.assertEqual(config_installer._valor_env("FLASK_SECRET_KEY=abc\n", "FLASK_SECRET_KEY"), "abc")


if __name__ == "__main__":
    unittest.main()
