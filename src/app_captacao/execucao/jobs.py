"""Estado em memoria das execucoes, por sessao do navegador.

Guarda as preferencias de execucao (email e destino), o ultimo resultado e o job
em andamento. O estado vive so no processo: reiniciar o app limpa o historico.

So uma automacao roda por vez no processo: o Edge da automacao (porta de
depuracao) e a pasta de downloads sao do computador, nao da sessao.
"""

from __future__ import annotations

import threading
import uuid
from copy import deepcopy

from flask import session

from app_captacao.core.shared.texto import normalize_text

_execution_preferences_cache: dict[str, dict[str, str]] = {}
_execution_results_cache: dict[str, dict] = {}
_execution_jobs: dict[str, dict] = {}
_execution_jobs_lock = threading.Lock()

# Jobs concluidos alem deste limite sao descartados (os mais antigos primeiro),
# para o processo nao acumular memoria em sessoes longas.
MAX_JOBS_CONCLUIDOS = 200
ESTADOS_EM_ANDAMENTO = {"pendente", "em_execucao"}


class ExecucaoEmAndamentoError(ValueError):
    """Ja existe uma automacao rodando neste computador."""


def _descartar_jobs_antigos() -> None:
    concluidos = [job_id for job_id, job in _execution_jobs.items() if job.get("estado") == "concluida"]
    for job_id in concluidos[: max(0, len(concluidos) - MAX_JOBS_CONCLUIDOS)]:
        _execution_jobs.pop(job_id, None)


def _get_execution_preferences_cache_key() -> str | None:
    user_id = session.get("user_id")
    if user_id:
        return f"user:{user_id}"

    user_login = normalize_text(session.get("user_login"))
    if user_login:
        return f"login:{user_login.lower()}"
    return None


def get_execution_preferences_for_current_session() -> dict[str, str]:
    cache_key = _get_execution_preferences_cache_key()
    if not cache_key:
        return {"email": "", "sharepoint_link": ""}

    stored = _execution_preferences_cache.get(cache_key, {})
    return {
        "email": normalize_text(stored.get("email")),
        "sharepoint_link": normalize_text(stored.get("sharepoint_link")),
    }


def set_execution_preferences_for_current_session(email: str, sharepoint_link: str) -> None:
    cache_key = _get_execution_preferences_cache_key()
    if not cache_key:
        return

    _execution_preferences_cache[cache_key] = {
        "email": normalize_text(email),
        "sharepoint_link": normalize_text(sharepoint_link),
    }


def clear_execution_preferences_for_current_session() -> None:
    cache_key = _get_execution_preferences_cache_key()
    if not cache_key:
        return
    _execution_preferences_cache.pop(cache_key, None)


def clear_execution_result_for_current_session() -> None:
    cache_key = _get_execution_preferences_cache_key()
    if cache_key:
        _execution_results_cache.pop(cache_key, None)


def get_last_execution_result_for_current_session() -> dict | None:
    cache_key = _get_execution_preferences_cache_key()
    if not cache_key:
        return None
    return _execution_results_cache.get(cache_key)


def set_last_execution_result_for_current_session(result: dict) -> None:
    cache_key = _get_execution_preferences_cache_key()
    if cache_key:
        _execution_results_cache[cache_key] = result


def get_current_execution_job() -> dict | None:
    job_id = session.get("execution_job_id")
    if not job_id:
        return None
    with _execution_jobs_lock:
        job = _execution_jobs.get(job_id)
        return deepcopy(job) if job else None


def get_execution_job(job_id: str) -> dict | None:
    with _execution_jobs_lock:
        job = _execution_jobs.get(job_id)
        return deepcopy(job) if job else None


def create_execution_job(tipo: str, relatorios: list[dict], operacao_nome: str = "") -> str:
    """Cria o job e o liga a sessao; recusa se outra automacao ainda estiver rodando."""
    job_id = uuid.uuid4().hex
    itens = [
        {
            "relatorio_id": relatorio.get("id") or relatorio.get("id_relatorio"),
            "relatorio_nome": relatorio.get("nome", ""),
            "operacao_nome": operacao_nome,
            "estado": "pendente",
            "mensagem": "Aguardando inicio.",
            "etapa": "",
            "caminho_final": "",
            "arquivos": [],
        }
        for relatorio in relatorios
    ]
    with _execution_jobs_lock:
        if any(job.get("estado") in ESTADOS_EM_ANDAMENTO for job in _execution_jobs.values()):
            raise ExecucaoEmAndamentoError(
                "Ja existe uma execucao em andamento neste computador. Aguarde ela terminar."
            )
        _descartar_jobs_antigos()
        _execution_jobs[job_id] = {
            "id": job_id,
            "tipo_execucao": tipo,
            "operacao_nome": operacao_nome,
            "estado": "pendente",
            "itens": itens,
            "quantidade_relatorios": len(itens),
            "quantidade_baixados": 0,
            "quantidade_nao_baixados": 0,
            "resumo": f"Preparando {len(itens)} relatorio(s).",
            "resultado": None,
        }
    session["execution_job_id"] = job_id
    return job_id


def update_execution_job(job_id: str, **updates) -> None:
    with _execution_jobs_lock:
        job = _execution_jobs.get(job_id)
        if job:
            job.update(updates)


def update_execution_job_item(job_id: str, relatorio_id, **updates) -> None:
    with _execution_jobs_lock:
        job = _execution_jobs.get(job_id)
        if not job:
            return
        for item in job["itens"]:
            if str(item.get("relatorio_id")) == str(relatorio_id):
                item.update(updates)
                break


def finish_execution_job(job_id: str, resultado: dict) -> None:
    with _execution_jobs_lock:
        job = _execution_jobs.get(job_id)
        if not job:
            return
        job.update(
            {
                "estado": "concluida",
                "itens": deepcopy(resultado.get("itens", [])),
                "quantidade_baixados": int(resultado.get("quantidade_baixados") or 0),
                "quantidade_nao_baixados": int(resultado.get("quantidade_nao_baixados") or 0),
                "resumo": resultado.get("resumo", "Execucao concluida."),
                "resultado": deepcopy(resultado),
            }
        )
