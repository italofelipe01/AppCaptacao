import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_captacao.inicializacao import dependencias, verificacoes
from app_captacao.inicializacao.verificacoes import AVISO, ERRO, OK


class DependenciasTests(unittest.TestCase):
    def _requisitos(self, texto):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "requirements.txt"
            caminho.write_text(texto, encoding="utf-8")
            return dependencias.ler_requisitos(caminho)

    def test_le_nome_especificador_e_ignora_comentarios(self):
        requisitos = self._requisitos("# comentario\nFlask>=3.0,<4.0\n\nopenpyxl>=3.1,<4.0  # planilhas\n-r outro.txt\n")
        self.assertEqual(
            requisitos,
            [dependencias.Requisito("Flask", ">=3.0,<4.0"), dependencias.Requisito("openpyxl", ">=3.1,<4.0")],
        )

    def test_marcador_de_plataforma_filtra_o_requisito(self):
        outra = "linux" if sys.platform == "win32" else "win32"
        requisitos = self._requisitos(f'a>=1; sys_platform == "{sys.platform}"\nb>=1; sys_platform == "{outra}"\n')
        self.assertEqual([r.nome for r in requisitos], ["a"])

    def test_compara_versoes_como_numeros_e_nao_como_texto(self):
        self.assertTrue(dependencias.versao_atende("3.10.2", ">=3.9,<4.0"))
        self.assertFalse(dependencias.versao_atende("4.0.0", ">=3.0,<4.0"))
        self.assertFalse(dependencias.versao_atende("2.9", ">=3.0"))
        self.assertTrue(dependencias.versao_atende("310", ">=306"))

    def test_aponta_biblioteca_ausente_e_fora_da_versao(self):
        def versao(nome):
            if nome == "ausente":
                raise dependencias.metadata.PackageNotFoundError(nome)
            return "1.0"

        requisitos = [
            dependencias.Requisito("ausente", ">=1"),
            dependencias.Requisito("antiga", ">=2"),
            dependencias.Requisito("certa", ">=1,<2"),
        ]
        with patch.object(dependencias.metadata, "version", side_effect=versao):
            pendencias = dependencias.verificar(requisitos)
        self.assertEqual([(p.requisito.nome, p.instalada) for p in pendencias], [("ausente", None), ("antiga", "1.0")])

    def test_requirements_do_projeto_esta_instalado_no_ambiente_de_teste(self):
        requisitos = dependencias.ler_requisitos(Path(__file__).resolve().parents[2] / "requirements.txt")
        nao_instaladas = [p.descrever() for p in dependencias.verificar(requisitos) if p.instalada is None]
        # pymssql e customtkinter sao opcionais fora do .venv do projeto.
        self.assertTrue(set(n.split(">")[0] for n in nao_instaladas) <= {"pymssql", "customtkinter"})


class VerificacoesTests(unittest.TestCase):
    def test_sem_arquivo_de_configuracao_impede_a_inicializacao(self):
        with patch("app_captacao.core.config.environment.initialize_environment", return_value=None):
            resultados = verificacoes.verificar_configuracao()
        self.assertEqual([r.status for r in resultados], [ERRO])

    def test_dados_do_banco_vazios_sao_erro_e_chave_vazia_e_aviso(self):
        env = {"DB_HOST": "", "DB_DATABASE": "", "DB_SCHEMA": "", "DB_USER": "", "DB_PASSWORD": "", "DB_EXTRA_PARAMS": "", "FLASK_SECRET_KEY": "", "APP_HOST": "127.0.0.1"}
        with patch.dict(os.environ, env), patch(
            "app_captacao.core.config.environment.initialize_environment", return_value=Path("teste.env")
        ):
            resultados = {r.nome: r for r in verificacoes.verificar_configuracao()}
        self.assertEqual(resultados["Dados do banco"].status, ERRO)
        for variavel in ("DB_HOST", "DB_DATABASE", "DB_USER", "DB_PASSWORD"):
            self.assertIn(variavel, resultados["Dados do banco"].mensagem)
        self.assertEqual(resultados["Chave de sessao"].status, AVISO)

    def test_conexao_confiavel_dispensa_usuario_e_senha_sql(self):
        env = {"DB_HOST": "srv", "DB_DATABASE": "db", "DB_USER": "", "DB_PASSWORD": "", "DB_EXTRA_PARAMS": "Trusted_Connection=yes", "FLASK_SECRET_KEY": "x", "APP_HOST": "127.0.0.1"}
        with patch.dict(os.environ, env), patch(
            "app_captacao.core.config.environment.initialize_environment", return_value=Path("teste.env")
        ), patch("app_captacao.core.config.environment.variaveis_herdadas_ignoradas", return_value=[]):
            resultados = verificacoes.verificar_configuracao()
        self.assertEqual([r.status for r in resultados], [OK])

    def test_variavel_do_windows_ignorada_e_avisada_so_pelo_nome(self):
        env = {"DB_HOST": "srv", "DB_DATABASE": "db", "DB_USER": "app", "DB_PASSWORD": "segredo", "DB_EXTRA_PARAMS": "", "FLASK_SECRET_KEY": "x", "APP_HOST": "127.0.0.1"}
        with patch.dict(os.environ, env), patch(
            "app_captacao.core.config.environment.initialize_environment", return_value=Path("teste.env")
        ), patch(
            "app_captacao.core.config.environment.variaveis_herdadas_ignoradas", return_value=["DB_USER", "DB_PASSWORD"]
        ):
            resultados = {r.nome: r for r in verificacoes.verificar_configuracao()}
        aviso = resultados["Variaveis do Windows"]
        self.assertEqual(aviso.status, AVISO)
        self.assertIn("DB_USER, DB_PASSWORD", aviso.mensagem)
        self.assertNotIn("segredo", aviso.mensagem + aviso.dica)

    def test_falha_no_banco_vira_erro_sem_expor_a_senha(self):
        with patch.dict(os.environ, {"DB_HOST": "srv", "DB_PASSWORD": "segredo"}), patch(
            "app_captacao.core.database.connection.get_db_connection", side_effect=RuntimeError("Login failed for user 'x'")
        ):
            resultado = verificacoes.verificar_banco()
        self.assertEqual(resultado.status, ERRO)
        self.assertIn("Login failed", resultado.mensagem)
        self.assertNotIn("segredo", resultado.mensagem)

    def test_erro_de_configuracao_interrompe_as_demais_verificacoes(self):
        with patch.object(verificacoes, "verificar_configuracao", return_value=[verificacoes.Resultado("Configuracao", ERRO, "x")]), patch.object(
            verificacoes, "verificar_banco"
        ) as banco:
            resultados = verificacoes.executar_verificacoes()
        banco.assert_not_called()
        self.assertEqual(len(resultados), 1)


if __name__ == "__main__":
    unittest.main()
