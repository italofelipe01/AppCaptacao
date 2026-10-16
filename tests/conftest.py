"""Protecao comum a todos os testes: nada e gravado na pasta de downloads real do usuario."""

import pytest

from app_captacao.automacao import downloads


@pytest.fixture(autouse=True)
def _pasta_de_downloads_temporaria(tmp_path, monkeypatch):
    # Sem destino, o arquivo final vai para <pasta de downloads>\<relatorio>\, e o padrao e
    # %USERPROFILE%\Downloads\Automação CAP.
    monkeypatch.setattr(downloads, "DOWNLOAD_DIR", str(tmp_path / "downloads"))
