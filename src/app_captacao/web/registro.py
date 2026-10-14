"""Coleta de rotas por modulo, registradas depois no app Flask.

O endpoint de cada rota e o nome da funcao, igual ao decorator do proprio Flask.
Os templates dependem desses nomes (url_for e request.endpoint), por isso nao se
usa Blueprint, que prefixaria o endpoint.
"""

from __future__ import annotations

from typing import Any, Callable

from flask import Flask


class RegistroRotas:
    def __init__(self) -> None:
        self._rotas: list[tuple[str, Callable[..., Any], dict[str, Any]]] = []

    def route(self, rule: str, **options: Any):
        def decorator(view: Callable[..., Any]) -> Callable[..., Any]:
            self._rotas.append((rule, view, options))
            return view

        return decorator

    def get(self, rule: str, **options: Any):
        return self.route(rule, methods=["GET"], **options)

    def post(self, rule: str, **options: Any):
        return self.route(rule, methods=["POST"], **options)

    def registrar(self, app: Flask) -> None:
        for rule, view, options in self._rotas:
            app.add_url_rule(rule, endpoint=view.__name__, view_func=view, **options)
