"""Abertura da interface web no navegador da maquina local."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def _wait_for_server(host: str, port: int, timeout_seconds: int = 15) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def _get_browser_host(host: str) -> str:
    normalized_host = (host or "").strip()
    if normalized_host in {"", "0.0.0.0", "::"}:
        return "127.0.0.1"
    return normalized_host


def _build_launch_url(host: str, port: int) -> str:
    browser_host = _get_browser_host(host)
    launch_url = (os.getenv("APP_LAUNCH_URL", "").strip() or "/")
    parsed = urlsplit(launch_url)
    if parsed.scheme and parsed.netloc:
        return launch_url

    path = parsed.path or "/"
    if not path.startswith("/"):
        path = f"/{path}"

    return urlunsplit(("http", f"{browser_host}:{port}", path, parsed.query, parsed.fragment))


def _get_chrome_path() -> str | None:
    chrome_candidates = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        shutil.which("google-chrome"),
        os.path.join(os.getenv("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.getenv("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for candidate in chrome_candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
    return None


def _open_url_in_browser(target_url: str) -> bool:
    chrome_path = _get_chrome_path()
    if chrome_path:
        try:
            subprocess.Popen([chrome_path, target_url])
            return True
        except OSError:
            pass

    if os.name == "nt" and hasattr(os, "startfile"):
        try:
            os.startfile(target_url)
            return True
        except OSError:
            pass

    try:
        return bool(webbrowser.open(target_url, new=2))
    except Exception:
        return False


def _open_browser_when_ready(host: str, port: int) -> None:
    target_url = _build_launch_url(host, port)
    if not _wait_for_server(host, port):
        return
    _open_url_in_browser(target_url)


def start_browser_thread(host: str, port: int) -> threading.Thread:
    browser_thread = threading.Thread(
        target=_open_browser_when_ready,
        args=(host, port),
        daemon=True,
    )
    browser_thread.start()
    return browser_thread
