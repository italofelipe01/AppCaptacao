"""
Script utilitario para abrir o navegador configurado e autenticar no Sienge.
"""

from __future__ import annotations

import argparse
import logging
import os
import time

from app_config import initialize_environment
from services.playwright_auth_service import autenticar_sienge_playwright


def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Abre o navegador configurado e executa somente a autenticacao no Sienge.",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("SIENGE_EMAIL", "").strip(),
        help="Email do usuario no Sienge. Padrao: variavel SIENGE_EMAIL.",
    )
    parser.add_argument(
        "--senha",
        default=os.getenv("SIENGE_SENHA", ""),
        help="Senha do usuario no Sienge. Padrao: variavel SIENGE_SENHA.",
    )
    parser.add_argument(
        "--fechar",
        action="store_true",
        help="Fecha o navegador logo apos autenticar.",
    )
    return parser


def main() -> int:
    initialize_environment()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    args = _criar_parser().parse_args()
    email = str(args.email or "").strip()
    senha = str(args.senha or "")

    if not email or not senha:
        raise ValueError(
            "Informe email e senha via argumentos --email/--senha ou pelas variaveis "
            "SIENGE_EMAIL e SIENGE_SENHA."
        )

    sessao = autenticar_sienge_playwright(email=email, senha=senha)

    print("Autenticacao no Sienge concluida com sucesso.")

    if args.fechar:
        sessao.quit()
        return 0

    print("O navegador sera mantido aberto. Pressione Ctrl+C para encerrar este script.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sessao.quit()
        print("Navegador encerrado pelo usuario.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
