"""Criptografia DPAPI do Windows, vinculada ao usuario e a maquina atuais.

Arquivos protegidos aqui so podem ser lidos pelo mesmo usuario na mesma maquina.
"""

from __future__ import annotations

import base64
import ctypes
import os


CRYPTPROTECT_UI_FORBIDDEN = 0x01


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def encrypt_text_for_current_user(plaintext: str) -> str:
    raw = _protect_bytes_for_current_user(plaintext.encode("utf-8"))
    return base64.b64encode(raw).decode("ascii")


def encrypt_bytes_for_current_user(payload: bytes) -> bytes:
    return _protect_bytes_for_current_user(payload)


def decrypt_text_for_current_user(encoded_payload: str) -> str:
    raw = base64.b64decode(encoded_payload.encode("ascii"))
    decrypted = _unprotect_bytes_for_current_user(raw)
    return decrypted.decode("utf-8")


def decrypt_bytes_for_current_user(payload: bytes) -> bytes:
    return _unprotect_bytes_for_current_user(payload)


def _protect_bytes_for_current_user(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Criptografia DPAPI disponivel apenas no Windows.")

    in_blob, in_buffer = _bytes_to_blob(data)
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _unprotect_bytes_for_current_user(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Criptografia DPAPI disponivel apenas no Windows.")

    in_blob, in_buffer = _bytes_to_blob(data)
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)


def _bytes_to_blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array]:
    buffer = (ctypes.c_byte * len(data))(*data) if data else (ctypes.c_byte * 1)()
    blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    return blob, buffer
