"""Downloads: deteccao de arquivo novo e estavel, renomeacao e copia para o destino.

Sucesso so e declarado depois que o arquivo existe, tem tamanho estavel e foi
confirmado no destino final.
"""

from __future__ import annotations

import logging
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from app_captacao.automacao.config import (
    DEBUG_ARTIFACTS_ENABLED,
    DOWNLOAD_DIR,
    DOWNLOAD_QUIET_PERIOD_SECONDS,
    DOWNLOAD_STABLE_CHECK_INTERVAL,
    DOWNLOAD_STABLE_CYCLES_REQUIRED,
    DOWNLOAD_TEMP_EXTENSIONS,
    DOWNLOAD_WAIT_TIMEOUT,
)
from app_captacao.automacao import erros

logger = logging.getLogger(__name__)


def marcar_inicio_download():
    pasta = Path(DOWNLOAD_DIR)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivos_antes = {}
    for arquivo in pasta.iterdir():
        if not arquivo.is_file():
            continue
        try:
            stat = arquivo.stat()
            arquivos_antes[str(arquivo.resolve())] = (stat.st_size, stat.st_mtime_ns)
        except OSError:
            continue
    return {"inicio_ns": time.time_ns(), "arquivos_antes": arquivos_antes}


def renomear_download_relatorio(relatorio_config, empresa_id="", inicio_download=None):
    inicio_download = inicio_download or marcar_inicio_download()
    arquivo = _aguardar_arquivo_download(inicio_download)
    if not arquivo:
        logger.warning(
            "Nenhum download novo encontrado para renomear | relatorio=%s | empresa=%s | pasta=%s",
            relatorio_config.get("nome", ""),
            empresa_id,
            DOWNLOAD_DIR,
        )
        raise erros.DownloadProcessingError(
            "download",
            f"Nenhum arquivo novo foi concluido em '{DOWNLOAD_DIR}'.",
        )

    nome_relatorio = sanitizar_nome_arquivo(relatorio_config.get("nome") or "relatorio")
    empresa = sanitizar_nome_arquivo(str(empresa_id or "sem_empresa"))
    data_atual = datetime.now().strftime("%Y-%m-%d")
    destino = montar_caminho_download_unico(
        arquivo.parent,
        f"{nome_relatorio}_{empresa}_{data_atual}",
        arquivo.suffix,
    )

    try:
        arquivo.rename(destino)
        if not destino.exists() or destino.stat().st_size <= 0:
            raise OSError("O arquivo renomeado nao foi confirmado no disco.")
        logger.info("Download renomeado | origem=%s | destino=%s", arquivo, destino)
    except OSError as exc:
        logger.exception("Nao foi possivel renomear o download %s.", arquivo)
        raise erros.DownloadProcessingError("renomeacao", f"Falha ao renomear o arquivo: {exc}") from exc

    caminho_final = str(destino)
    if str(relatorio_config.get("sharepoint_link", "") or "").strip():
        caminho_final = copiar_download_para_sharepoint(
            relatorio_config,
            destino,
            registrar_resultado=False,
        )
    relatorio_config.setdefault("_arquivos_finais", []).append(caminho_final)
    # Os modulos de consolidacao continuam trabalhando com o arquivo local;
    # o caminho copiado e registrado separadamente como resultado final.
    return str(destino)


def _aguardar_arquivo_download(inicio_download):
    pasta = Path(DOWNLOAD_DIR)
    pasta.mkdir(parents=True, exist_ok=True)
    prazo = time.time() + DOWNLOAD_WAIT_TIMEOUT
    estabilidade_por_arquivo = {}

    if isinstance(inicio_download, dict):
        inicio_ns = int(inicio_download.get("inicio_ns") or 0)
        arquivos_antes = inicio_download.get("arquivos_antes") or {}
    else:
        inicio_ns = int(float(inicio_download or 0) * 1_000_000_000)
        arquivos_antes = {}

    def arquivo_novo_ou_alterado(arquivo, stat):
        assinatura_anterior = arquivos_antes.get(str(arquivo.resolve()))
        if assinatura_anterior is None:
            return stat.st_mtime_ns >= inicio_ns
        return (stat.st_size, stat.st_mtime_ns) != tuple(assinatura_anterior) and stat.st_mtime_ns >= inicio_ns

    while time.time() <= prazo:
        downloads_em_andamento = []
        candidatos = []
        for arquivo in pasta.iterdir():
            if not arquivo.is_file():
                continue
            try:
                stat = arquivo.stat()
            except OSError:
                continue
            if not arquivo_novo_ou_alterado(arquivo, stat):
                continue
            if arquivo.suffix.lower() in DOWNLOAD_TEMP_EXTENSIONS:
                downloads_em_andamento.append(arquivo)
            else:
                candidatos.append(arquivo)

        if candidatos and not downloads_em_andamento:
            candidato = max(candidatos, key=lambda item: item.stat().st_mtime)
            tamanho_atual = candidato.stat().st_size
            if tamanho_atual <= 0:
                estabilidade_por_arquivo[candidato] = (tamanho_atual, 0)
            else:
                tamanho_anterior, ciclos_estaveis = estabilidade_por_arquivo.get(candidato, (None, 0))
                if tamanho_anterior == tamanho_atual:
                    ciclos_estaveis += 1
                else:
                    ciclos_estaveis = 1
                estabilidade_por_arquivo[candidato] = (tamanho_atual, ciclos_estaveis)
            if (
                tamanho_atual > 0
                and estabilidade_por_arquivo.get(candidato, (None, 0))[1] >= DOWNLOAD_STABLE_CYCLES_REQUIRED
            ):
                return candidato

        time.sleep(DOWNLOAD_STABLE_CHECK_INTERVAL)

    return ""


def aguardar_pasta_download_estabilizar(timeout=DOWNLOAD_WAIT_TIMEOUT):
    pasta = Path(DOWNLOAD_DIR)
    prazo = time.time() + timeout

    while time.time() <= prazo:
        agora = time.time()
        downloads_em_andamento = []
        atividade_recente = []

        for arquivo in pasta.iterdir():
            if not arquivo.is_file():
                continue
            try:
                stat = arquivo.stat()
            except OSError:
                continue

            if arquivo.suffix.lower() in DOWNLOAD_TEMP_EXTENSIONS:
                downloads_em_andamento.append(arquivo)
                continue

            if stat.st_mtime >= agora - DOWNLOAD_QUIET_PERIOD_SECONDS:
                atividade_recente.append(arquivo)

        if not downloads_em_andamento and not atividade_recente:
            return True

        time.sleep(DOWNLOAD_STABLE_CHECK_INTERVAL)

    logger.warning(
        "A pasta de downloads nao estabilizou no tempo esperado | pasta=%s | timeout=%ss",
        DOWNLOAD_DIR,
        timeout,
    )
    return False


def montar_caminho_download_unico(pasta, nome_base, extensao):
    destino = pasta / f"{nome_base}{extensao}"
    contador = 2

    while destino.exists():
        destino = pasta / f"{nome_base}_{contador}{extensao}"
        contador += 1

    return destino


def capture_debug_snapshot(driver, nome):
    if not DEBUG_ARTIFACTS_ENABLED:
        return {}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    debug_dir = Path(DOWNLOAD_DIR) / "_debug_selenium"
    debug_dir.mkdir(parents=True, exist_ok=True)
    nome_base = sanitizar_nome_arquivo(nome or "snapshot")
    png_path = debug_dir / f"{timestamp}_{nome_base}.png"
    html_path = debug_dir / f"{timestamp}_{nome_base}.html"

    try:
        driver.save_screenshot(str(png_path))
    except Exception:
        logger.exception("Falha ao salvar screenshot de debug %s.", png_path)

    try:
        html_path.write_text(driver.page_source, encoding="utf-8")
    except Exception:
        logger.exception("Falha ao salvar HTML de debug %s.", html_path)

    logger.info("Snapshot de debug salvo | png=%s | html=%s", png_path, html_path)
    return {"png": str(png_path), "html": str(html_path)}


def sanitizar_nome_arquivo(valor):
    valor = str(valor or "").strip()
    valor = re.sub(r'[<>:"/\\|?*]+', " ", valor)
    valor = re.sub(r"\s+", " ", valor).strip()
    return valor or "sem_nome"


def copiar_download_para_sharepoint(relatorio_config, arquivo_origem, registrar_resultado=True):
    arquivo_origem = Path(arquivo_origem)
    destino_informado = str(relatorio_config.get("sharepoint_link", "") or "").strip()
    if not destino_informado:
        caminho_final = str(arquivo_origem)
        if registrar_resultado:
            relatorio_config.setdefault("_arquivos_finais", []).append(caminho_final)
        return caminho_final

    destino_base = _resolver_destino_sharepoint(relatorio_config.get("sharepoint_link", ""))
    if not destino_base:
        raise erros.DownloadProcessingError(
            "copia",
            "O destino informado nao e uma pasta local sincronizada ou caminho UNC valido.",
        )

    try:
        destino_base.mkdir(parents=True, exist_ok=True)
        destino_arquivo = montar_caminho_download_unico(
            destino_base,
            arquivo_origem.stem,
            arquivo_origem.suffix,
        )
        shutil.copy2(arquivo_origem, destino_arquivo)
        if not destino_arquivo.exists() or destino_arquivo.stat().st_size != arquivo_origem.stat().st_size:
            raise OSError("A copia no destino nao foi confirmada ou ficou incompleta.")
        logger.info("Download copiado para SharePoint/local | origem=%s | destino=%s", arquivo_origem, destino_arquivo)
        caminho_final = str(destino_arquivo)
        if registrar_resultado:
            relatorio_config.setdefault("_arquivos_finais", []).append(caminho_final)
        return caminho_final
    except OSError as exc:
        logger.exception(
            "Nao foi possivel copiar o arquivo %s para o destino SharePoint/local '%s'.",
            arquivo_origem,
            destino_base,
        )
        raise erros.DownloadProcessingError("copia", f"Falha ao copiar o arquivo para o destino: {exc}") from exc


def _resolver_destino_sharepoint(sharepoint_link):
    destino = str(sharepoint_link or "").strip()
    if not destino:
        return None

    if destino.lower().startswith(("http://", "https://")):
        logger.warning(
            "URL web do SharePoint informada (%s), mas upload direto por URL ainda nao esta implementado. "
            "Use uma pasta local sincronizada/UNC para copia automatica.",
            destino,
        )
        return None

    caminho = Path(destino).expanduser()
    if caminho.name.strip().lower() == "automação cap".lower():
        return caminho

    return caminho / "Automação CAP"
