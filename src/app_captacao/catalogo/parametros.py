"""Linhas da aba Parâmetros do consolidado (docs/specs/parametros-no-consolidado.md).

Uma linha por filtro que a automação recebeu: o nome no cadastro, o campo da tela do Sienge
que recebeu o valor, o valor e uma observação quando o valor não veio do cadastro ou não foi
aplicado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app_captacao.catalogo import regras
from app_captacao.catalogo.campos_sienge import DATA, CampoSienge, normalizar
from app_captacao.core.shared.texto import normalize_text

SEM_VALOR = "—"
PREENCHIDO_AUTOMATICAMENTE = "Preenchido automaticamente"
NAO_INFORMADO = "Não informado: o Sienge usa o padrão da tela"
ACAO_AUTOMATICA = "Ação automática"
SEM_CAMPO_NO_SIENGE = "NÃO APLICADO: sem campo correspondente na tela do Sienge"
NENHUM_FILTRO = "Nenhum filtro cadastrado para este relatório"

_FORMATOS_DE_DATA = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%d%m%Y")


@dataclass(frozen=True)
class LinhaParametro:
    filtro: str
    campo_no_sienge: str
    valor: str
    observacao: str = ""


def _data(valor: object) -> str:
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%d/%m/%Y")
    texto = normalize_text(valor)
    for formato in _FORMATOS_DE_DATA:
        try:
            return datetime.strptime(texto, formato).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return texto


def _formatar(filtro: dict, campo: CampoSienge | None) -> str:
    valor = filtro.get("valor")
    eh_data = (campo is not None and campo.tipo == DATA) or normalize_text(filtro.get("tipo_campo_valor")).upper() == "DATE"
    if eh_data:
        return _data(valor)
    partes = valor if isinstance(valor, list) else str(valor or "").split(",")
    return ", ".join(texto for texto in (normalize_text(parte) for parte in partes) if texto)


def _linha(filtro: dict, campo: CampoSienge | None) -> LinhaParametro:
    nome = normalize_text(filtro.get("nome") or filtro.get("nome_filtro")) or f"Filtro {filtro.get('id')}"
    valor = _formatar(filtro, campo)
    if campo is None:
        if not regras.acao_exige_valor(filtro.get("acao")) or filtro.get("automatico"):
            return LinhaParametro(nome, SEM_VALOR, valor or SEM_VALOR, ACAO_AUTOMATICA)
        return LinhaParametro(nome, SEM_VALOR, valor or SEM_VALOR, SEM_CAMPO_NO_SIENGE)
    if campo.valor_fixo:
        observacao = PREENCHIDO_AUTOMATICAMENTE
        if valor and normalizar(valor) != normalizar(campo.valor_fixo):
            observacao = f"{PREENCHIDO_AUTOMATICAMENTE}; o valor do cadastro ('{valor}') não é aplicado"
        return LinhaParametro(nome, campo.rotulo, campo.valor_fixo, observacao)
    if not valor:
        padrao = f" ({campo.padrao_na_tela})" if campo.padrao_na_tela else ""
        return LinhaParametro(nome, campo.rotulo, SEM_VALOR, f"{NAO_INFORMADO}{padrao}")
    return LinhaParametro(nome, campo.rotulo, valor)


def linhas_de_parametros(relatorio: dict | None) -> list[LinhaParametro]:
    """Linhas da aba, na ordem do cadastro; uma linha de aviso quando não há filtros."""
    filtros, campos = regras.campos_dos_filtros(relatorio or {})
    linhas = [_linha(filtro, campo) for filtro, campo in zip(filtros, campos)]
    return linhas or [LinhaParametro(NENHUM_FILTRO, SEM_VALOR, SEM_VALOR)]
