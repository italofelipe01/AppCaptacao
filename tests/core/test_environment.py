import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app_captacao.core.config import environment


class WritableStateDirTests(unittest.TestCase):
    def test_writable_state_falls_back_when_appdata_is_denied(self):
        fallback_dir = Path(tempfile.gettempdir()) / f"appcaptacao_state_test_{uuid.uuid4().hex}"
        denied_dir = fallback_dir.parent / f"denied_{uuid.uuid4().hex}"

        def ensure_directory(path):
            if Path(path) == denied_dir:
                raise PermissionError(5, "Acesso negado", str(path))
            Path(path).mkdir(parents=True, exist_ok=True)
            return Path(path)

        try:
            with patch.object(environment, "get_state_dir", return_value=denied_dir), patch.object(
                environment, "get_temporary_state_dir", return_value=fallback_dir
            ), patch.object(environment, "_ensure_writable_directory", side_effect=ensure_directory):
                self.assertEqual(environment.get_writable_state_dir(), fallback_dir)
        finally:
            if fallback_dir.exists():
                fallback_dir.rmdir()



class EnvironmentLoadingTests(unittest.TestCase):
    def test_automation_settings_see_values_from_env_file(self):
        # Antes, o modulo de automacao lia os.getenv no import, antes de o .env ser
        # carregado, e o executavel ignorava SELENIUM_DOWNLOAD_DIR e afins.
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            pasta = Path(tmp) / "downloads_teste"
            env_file.write_text(f"SELENIUM_DOWNLOAD_DIR={pasta}\nSELENIUM_BROWSER=chrome\n", encoding="utf-8")
            script = (
                "import sys; from pathlib import Path\n"
                "from app_captacao.core.config import environment\n"
                f"environment.get_config_path_candidates = lambda: [Path(r'{env_file}')]\n"
                "from app_captacao.automacao import config\n"
                "print(config.DOWNLOAD_DIR); print(config.SELENIUM_BROWSER)\n"
            )
            child_env = {k: v for k, v in os.environ.items() if not k.startswith(("SELENIUM_", "EDGE_"))}
            child_env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
            saida = subprocess.run(
                [sys.executable, "-c", script], capture_output=True, text=True, env=child_env, check=True
            ).stdout.splitlines()

        self.assertEqual(saida, [str(pasta), "chrome"])

    def test_initialize_environment_reads_configuration_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("APP_CAPTACAO_TESTE_IDEMPOTENTE=1\n", encoding="utf-8")
            with patch.object(environment, "_environment_loaded", False), patch.object(
                environment, "_loaded_config_path", None
            ), patch.object(
                environment, "get_config_path_candidates", return_value=[env_file]
            ), patch.object(environment, "_load_environment_from_path") as carregar:
                self.assertEqual(environment.initialize_environment(), env_file)
                self.assertEqual(environment.initialize_environment(), env_file)
        carregar.assert_called_once_with(env_file)

    def test_arquivo_vale_sobre_variavel_herdada_do_windows(self):
        # 2026-10-20: DB_USER/DB_PASSWORD/DB_DATABASE de outro projeto no ambiente do usuario
        # encobriam o .env e o banco recusava o login (18456).
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "DB_USER=conta_do_app\nDB_HOST=servidor_do_app\nAPP_HOST=127.0.0.1\n", encoding="utf-8"
            )
            script = (
                "from pathlib import Path\n"
                "from app_captacao.core.config import environment\n"
                f"environment.get_config_path_candidates = lambda: [Path(r'{env_file}')]\n"
                "environment.initialize_environment()\n"
                "import os\n"
                "print(os.environ['DB_USER']); print(os.environ['DB_HOST'])\n"
                "print(','.join(environment.variaveis_herdadas_ignoradas()))\n"
            )
            child_env = {k: v for k, v in os.environ.items() if not k.startswith(("DB_", "APP_HOST"))}
            child_env.update(DB_USER="conta_de_outro_projeto", APP_HOST="127.0.0.1")
            child_env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
            saida = subprocess.run(
                [sys.executable, "-c", script], capture_output=True, text=True, env=child_env, check=True
            ).stdout.splitlines()

        # APP_HOST herdado com o mesmo valor nao e "ignorado": so o que mudou e avisado.
        self.assertEqual(saida, ["conta_do_app", "servidor_do_app", "DB_USER"])

    def test_recarga_nao_confunde_valor_do_arquivo_anterior_com_variavel_do_windows(self):
        with patch.object(environment, "_AMBIENTE_HERDADO", {}), patch.dict(os.environ, {}, clear=False):
            environment._variaveis_herdadas_ignoradas.clear()
            environment._aplicar_configuracao({"APP_CAPTACAO_TESTE_RECARGA": "primeiro"})
            environment._aplicar_configuracao({"APP_CAPTACAO_TESTE_RECARGA": "segundo"})
            self.assertEqual(os.environ["APP_CAPTACAO_TESTE_RECARGA"], "segundo")
            self.assertEqual(environment.variaveis_herdadas_ignoradas(), [])

    def test_development_prefers_root_env_and_never_reads_legacy_folder(self):
        with patch.object(environment, "is_frozen_runtime", return_value=False):
            candidatos = environment.get_config_path_candidates()
        self.assertEqual(candidatos[0], environment.PROJECT_ROOT / ".env")
        self.assertFalse(any("oldversion" in str(caminho) for caminho in candidatos))


if __name__ == "__main__":
    unittest.main()
