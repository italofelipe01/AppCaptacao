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
    DOWNLOAD_TEMP_STALE_SECONDS,
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


def renomear_download_relatorio(relatorio_config, empresa_id="", inicio_download=None, registrar_resultado=True):
    """Espera o download, renomeia e devolve o caminho local.

    Com registrar_resultado=True o arquivo tambem e copiado para o destino e entra no
    resultado do relatorio. Relatorios paginados usam False em cada pagina e registram
    so o arquivo final (a pagina unica ou o consolidado).
    """
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

    if registrar_resultado:
        copiar_download_para_sharepoint(relatorio_config, destino)
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
                candidatos.append((arquivo, stat))

        if candidatos and not downloads_em_andamento:
            # Usa o stat da listagem: o navegador pode renomear ou remover o arquivo
            # entre a listagem e uma nova leitura.
            candidato, stat_candidato = max(candidatos, key=lambda item: item[1].st_mtime)
            tamanho_atual = stat_candidato.st_size
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


def aguardar_pasta_download_estabilizar(timeout: float = DOWNLOAD_WAIT_TIMEOUT):
    """True quando nenhum download esta em andamento e nada foi gravado recentemente.

    Temporario parado ha mais de SELENIUM_DOWNLOAD_STALE_TEMP_SECONDS (download
    interrompido em outra execucao, por exemplo) nao conta como download em andamento.
    """
    pasta = Path(DOWNLOAD_DIR)
    prazo = time.time() + timeout
    abandonados_avisados: set[str] = set()

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
                if stat.st_mtime >= agora - DOWNLOAD_TEMP_STALE_SECONDS:
                    downloads_em_andamento.append(arquivo)
                elif arquivo.name not in abandonados_avisados:
                    abandonados_avisados.add(arquivo.name)
                    logger.warning(
                        "Temporario de download parado ha mais de %ss ignorado: %s. Pode ser apagado.",
                        DOWNLOAD_TEMP_STALE_SECONDS,
                        arquivo,
                    )
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
            _registrar_arquivo_final(relatorio_config, caminho_final)
        return caminho_final

    motivo = mensagem_destino_invalido(destino_informado)
    if motivo:
        raise erros.DownloadProcessingError("copia", motivo)
    destino_base = _resolver_destino_sharepoint(destino_informado)

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
    except OSError as exc:
        logger.exception(
            "Nao foi possivel copiar o arquivo %s para o destino SharePoint/local '%s'.",
            arquivo_origem,
            destino_base,
        )
        raise erros.DownloadProcessingError("copia", f"Falha ao copiar o arquivo para o destino: {exc}") from exc
    if registrar_resultado:
        _registrar_arquivo_final(relatorio_config, caminho_final)
    return caminho_final


def _registrar_arquivo_final(relatorio_config, caminho_final):
    """Arquivo confirmado no destino: entra no resultado e e avisado na tela."""
    relatorio_config.setdefault("_arquivos_finais", []).append(caminho_final)
    avisar = relatorio_config.get("_ao_registrar_arquivo")
    if callable(avisar):
        try:
            avisar(caminho_final)
        except Exception:
            logger.warning("Nao foi possivel atualizar o andamento na tela.", exc_info=True)


def mensagem_destino_invalido(destino) -> str:
    """Motivo para recusar o destino informado na tela; vazio quando o destino serve.

    O destino e uma pasta sincronizada do SharePoint/OneDrive ou um caminho de rede.
    Caminho relativo cairia numa pasta relativa a de onde o app foi aberto.
    """
    destino = str(destino or "").strip()
    if not destino:
        return ""
    if destino.lower().startswith(("http://", "https://")):
        return (
            "Link do SharePoint nao e aceito como destino: informe a pasta sincronizada no "
            "computador ou um caminho de rede (\\\\servidor\\pasta)."
        )
    if not Path(destino).expanduser().is_absolute():
        return (
            "O destino precisa ser um caminho completo, como C:\\Users\\voce\\SharePoint\\Pasta "
            "ou \\\\servidor\\pasta."
        )
    return ""


def _resolver_destino_sharepoint(destino):
    caminho = Path(str(destino).strip()).expanduser()
    if caminho.name.strip().lower() == "automação cap":
        return caminho
    return caminho / "Automação CAP"
