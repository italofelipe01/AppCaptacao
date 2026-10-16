import errno
import os
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


class PastaDeDownloadsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _estabilizou(self):
        with patch.object(downloads, "DOWNLOAD_DIR", str(self.directory)), patch.object(
            downloads, "DOWNLOAD_STABLE_CHECK_INTERVAL", 0.01
        ), patch.object(downloads, "DOWNLOAD_QUIET_PERIOD_SECONDS", 0.05), patch.object(
            downloads, "DOWNLOAD_TEMP_STALE_SECONDS", 60
        ):
            return downloads.aguardar_pasta_download_estabilizar(timeout=0.2)

    def test_temporario_abandonado_nao_trava_a_pasta(self):
        abandonado = self.directory / "Unconfirmed 123.crdownload"
        abandonado.write_bytes(b"x")
        duas_horas_atras = time.time() - 7200
        os.utime(abandonado, (duas_horas_atras, duas_horas_atras))
        self.assertTrue(self._estabilizou())

    def test_temporario_em_andamento_trava_a_pasta(self):
        (self.directory / "Unconfirmed 456.crdownload").write_bytes(b"x")
        self.assertFalse(self._estabilizou())


class DestinoTests(unittest.TestCase):
    def test_destino_vazio_e_caminho_completo_sao_aceitos(self):
        self.assertEqual(downloads.mensagem_destino_invalido(""), "")
        self.assertEqual(downloads.mensagem_destino_invalido(r"C:\Users\ana\SharePoint\Relatorios"), "")
        self.assertEqual(downloads.mensagem_destino_invalido(r"\\servidor\captacao"), "")

    def test_link_web_e_caminho_relativo_sao_recusados(self):
        self.assertIn("Link do SharePoint", downloads.mensagem_destino_invalido("https://empresa.sharepoint.com/sites/x"))
        self.assertIn("caminho completo", downloads.mensagem_destino_invalido("Relatorios"))
        self.assertIn("caminho completo", downloads.mensagem_destino_invalido("C:Relatorios"))

    def test_copia_para_destino_relativo_falha_na_etapa_copia(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "relatorio.xlsx"
            arquivo.write_bytes(b"conteudo")
            with self.assertRaises(downloads.erros.DownloadProcessingError) as erro:
                downloads.copiar_download_para_sharepoint({"sharepoint_link": "Relatorios"}, arquivo)
        self.assertEqual(erro.exception.etapa, "copia")

    def test_arquivo_final_registrado_avisa_a_tela(self):
        avisos = []
        relatorio = {"nome": "Vendas", "_ao_registrar_arquivo": avisos.append}
        with tempfile.TemporaryDirectory() as pasta, patch.object(downloads, "DOWNLOAD_DIR", pasta):
            arquivo = Path(pasta) / "Vendas_1_2026-10-15.xlsx"
            arquivo.write_bytes(b"conteudo")
            downloads.copiar_download_para_sharepoint(relatorio, arquivo)
            final = Path(pasta) / "Vendas" / "Vendas_1_2026-10-15.xlsx"
        self.assertEqual(avisos, [str(final)])
        self.assertEqual(relatorio["_arquivos_finais"], [str(final)])

    def test_sem_destino_o_arquivo_e_movido_para_a_pasta_do_relatorio(self):
        with tempfile.TemporaryDirectory() as pasta, patch.object(downloads, "DOWNLOAD_DIR", pasta):
            arquivo = Path(pasta) / "Unidades_92_2026-10-16.xlsx"
            arquivo.write_bytes(b"conteudo")
            final = downloads.copiar_download_para_sharepoint({"nome": "Unidades"}, arquivo)
            self.assertEqual(Path(final), Path(pasta) / "Unidades" / "Unidades_92_2026-10-16.xlsx")
            self.assertTrue(Path(final).exists())
            self.assertFalse(arquivo.exists())

    def test_destino_igual_a_pasta_de_downloads_nao_deixa_arquivo_repetido(self):
        # Caso real: destino e pasta de downloads eram a mesma pasta e cada arquivo saia duas vezes (_2).
        with tempfile.TemporaryDirectory() as raiz:
            pasta_downloads = Path(raiz) / "Automação CAP"
            pasta_downloads.mkdir()
            arquivo = pasta_downloads / "Mapa de Vendas_242_2026-10-16.xlsx"
            arquivo.write_bytes(b"conteudo")
            destino_escrito_diferente = str(pasta_downloads).upper() + "\\"
            relatorio = {"nome": "Mapa de Vendas", "sharepoint_link": destino_escrito_diferente}
            with patch.object(downloads, "DOWNLOAD_DIR", str(pasta_downloads)):
                final = downloads.copiar_download_para_sharepoint(relatorio, arquivo)
            todos = sorted(p.relative_to(pasta_downloads).as_posix() for p in pasta_downloads.rglob("*.xlsx"))
        self.assertEqual(todos, ["Mapa de Vendas/Mapa de Vendas_242_2026-10-16.xlsx"])
        self.assertEqual(relatorio["_arquivos_finais"], [final])

    def test_destino_em_outra_pasta_recebe_copia_na_pasta_do_relatorio(self):
        with tempfile.TemporaryDirectory() as raiz:
            pasta_downloads = Path(raiz) / "downloads"
            pasta_downloads.mkdir()
            arquivo = pasta_downloads / "Vendas_242_2026-10-16.xlsx"
            arquivo.write_bytes(b"conteudo")
            relatorio = {"nome": "Relatório de Vendas", "sharepoint_link": str(Path(raiz) / "SharePoint")}
            with patch.object(downloads, "DOWNLOAD_DIR", str(pasta_downloads)):
                final = downloads.copiar_download_para_sharepoint(relatorio, arquivo)
            esperado = Path(raiz) / "SharePoint" / "Automação CAP" / "Relatório de Vendas" / arquivo.name
            self.assertEqual(Path(final), esperado)
            self.assertEqual(esperado.read_bytes(), b"conteudo")
            self.assertTrue(arquivo.exists())

    def test_renomear_sem_destino_devolve_o_arquivo_na_pasta_do_relatorio(self):
        with tempfile.TemporaryDirectory() as pasta:
            baixado = Path(pasta) / "export.xlsx"
            baixado.write_bytes(b"relatorio")
            relatorio = {"nome": "Unidades"}
            with patch.object(downloads, "DOWNLOAD_DIR", pasta), patch.object(
                downloads, "_aguardar_arquivo_download", return_value=baixado
            ):
                caminho = downloads.renomear_download_relatorio(relatorio, "92", {})
            self.assertTrue(Path(caminho).exists())
            self.assertEqual(Path(caminho).parent, Path(pasta) / "Unidades")
            self.assertEqual(relatorio["_arquivos_finais"], [caminho])
            self.assertEqual(list(Path(pasta).glob("*.xlsx")), [])

    def test_pagina_intermediaria_nao_entra_no_resultado(self):
        with tempfile.TemporaryDirectory() as pasta:
            baixado = Path(pasta) / "export.xlsx"
            relatorio = {"nome": "Saldo devedor", "sharepoint_link": str(Path(pasta) / "destino")}
            with patch.object(downloads, "DOWNLOAD_DIR", pasta), patch.object(
                downloads, "_aguardar_arquivo_download", return_value=baixado
            ):
                baixado.write_bytes(b"pagina")
                local = downloads.renomear_download_relatorio(relatorio, "1_p1", {}, registrar_resultado=False)
            self.assertTrue(Path(local).exists())
            self.assertNotIn("_arquivos_finais", relatorio)
            self.assertFalse((Path(pasta) / "destino").exists())


if __name__ == "__main__":
    unittest.main()
