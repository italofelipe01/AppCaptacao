"""Normalizacao de valores vindos de formulario ou do banco."""

from __future__ import annotations

from datetime import datetime


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def to_bool(value: object) -> bool:
    return str(value or "").strip() in {"1", "true", "True"}


def format_datetime(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    try:
        return datetime.fromisoformat(str(value)).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(value)
