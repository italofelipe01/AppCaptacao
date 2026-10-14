import errno
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app_captacao.automacao import downloads


class DownloadWatcherTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_download_watcher_does_not_reuse_preexisting_file(self):
        old_file = self.directory / f"relatorio_antigo_{uuid.uuid4().hex}.xlsx"
        old_file.write_bytes(b"old")
        with patch.object(downloads, "DOWNLOAD_DIR", str(self.directory)), patch.object(
            downloads, "DOWNLOAD_WAIT_TIMEOUT", 0.08
        ), patch.object(downloads, "DOWNLOAD_STABLE_CHECK_INTERVAL", 0.01):
            marker = downloads.marcar_inicio_download()
            result = downloads._aguardar_arquivo_download(marker)
        self.assertEqual(result, "")

    def test_download_watcher_accepts_only_a_new_stable_file(self):
        new_file = self.directory / f"novo_{uuid.uuid4().hex}.xlsx"
        with patch.object(downloads, "DOWNLOAD_DIR", str(self.directory)), patch.object(
            downloads, "DOWNLOAD_WAIT_TIMEOUT", 0.3
        ), patch.object(downloads, "DOWNLOAD_STABLE_CHECK_INTERVAL", 0.01), patch.object(
            downloads, "DOWNLOAD_STABLE_CYCLES_REQUIRED", 2
        ):
            marker = downloads.marcar_inicio_download()
            time.sleep(0.002)
            new_file.write_bytes(b"complete")
            result = downloads._aguardar_arquivo_download(marker)
        self.assertEqual(result, new_file)

    def test_arquivo_renomeado_durante_a_verificacao_nao_derruba_o_monitor(self):
        arquivo = self.directory / f"relatorio_{uuid.uuid4().hex}.xlsx"
        stat_original = Path.stat
        chamadas = {"total": 0}

        def stat_instavel(path, *args, **kwargs):
            if path == arquivo:
                chamadas["total"] += 1
                if chamadas["total"] == 3:
                    raise FileNotFoundError(errno.ENOENT, "arquivo renomeado pelo navegador", str(path))
            return stat_original(path, *args, **kwargs)

        with patch.object(downloads, "DOWNLOAD_DIR", str(self.directory)), patch.object(
            downloads, "DOWNLOAD_WAIT_TIMEOUT", 0.5
        ), patch.object(downloads, "DOWNLOAD_STABLE_CHECK_INTERVAL", 0.01), patch.object(
            downloads, "DOWNLOAD_STABLE_CYCLES_REQUIRED", 2
        ):
            marker = downloads.marcar_inicio_download()
            time.sleep(0.002)
            arquivo.write_bytes(b"conteudo")
            with patch.object(Path, "stat", autospec=True, side_effect=stat_instavel):
                result = downloads._aguardar_arquivo_download(marker)
        self.assertEqual(result, arquivo)


if __name__ == "__main__":
    unittest.main()
