"""Verificacoes de configuracao e pre-requisitos antes de abrir o app.

So rodam depois que as bibliotecas estao instaladas. Cada verificacao devolve
um Resultado: "erro" impede a inicializacao; "aviso" so informa.
"""

from __future__ import annotations

import os
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

OK = "ok"
AVISO = "aviso"
ERRO = "erro"


@dataclass(frozen=True)
class Resultado:
    nome: str
    status: str
    mensagem: str
    dica: str = ""


def verificar_configuracao() -> list[Resultado]:
    from app_captacao.core.config import environment

    caminho = environment.initialize_environment()
    if caminho is None:
        return [
            Resultado(
                "Configuracao",
                ERRO,
                "Nenhum arquivo de configuracao foi encontrado.",
                "Copie .env.example para .env na raiz do projeto e preencha os dados do banco, "
                "ou use o ConfigurarAppCaptacao.exe no computador do usuario.",
            )
        ]

    resultados = [Resultado("Configuracao", OK, f"Carregada de {caminho}")]

    ignoradas = environment.variaveis_herdadas_ignoradas()
    if ignoradas:
        resultados.append(
            Resultado(
                "Variaveis do Windows",
                AVISO,
                f"Ignoradas, vale o arquivo de configuracao: {', '.join(ignoradas)}.",
                "Elas existem no ambiente do Windows com outro valor (de outro projeto, por exemplo). "
                "Para mudar o AppCaptacao, altere o arquivo de configuracao.",
            )
        )

    from app_captacao.core.database.connection import nome_do_banco

    faltando = [nome for nome in ("DB_HOST",) if not os.getenv(nome, "").strip()]
    # Mesma regra da conexao: DB_DATABASE vazio nao cai para DB_SCHEMA.
    if not nome_do_banco():
        faltando.append("DB_DATABASE")
    conexao_confiavel = "trusted_connection=yes" in os.getenv("DB_EXTRA_PARAMS", "").replace(" ", "").lower()
    if not conexao_confiavel:
        faltando += [nome for nome in ("DB_USER", "DB_PASSWORD") if not os.getenv(nome, "").strip()]
    if faltando:
        resultados.append(
            Resultado(
                "Dados do banco",
                ERRO,
                f"Variaveis obrigatorias vazias: {', '.join(faltando)}.",
                f"Preencha essas variaveis em {caminho}.",
            )
        )

    if not os.getenv("FLASK_SECRET_KEY", "").strip():
        resultados.append(
            Resultado(
                "Chave de sessao",
                AVISO,
                "FLASK_SECRET_KEY vazia: todos serao deslogados a cada reinicio do app.",
                'Gere uma com: python -c "import secrets; print(secrets.token_urlsafe(48))"',
            )
        )

    if os.getenv("APP_HOST", "127.0.0.1").strip() in {"0.0.0.0", "::"}:
        resultados.append(
            Resultado(
                "Acesso pela rede",
                AVISO,
                "APP_HOST=0.0.0.0 deixa o app acessivel por outros computadores da rede.",
                "Use APP_HOST=127.0.0.1 se o app for usado so nesta maquina.",
            )
        )

    if os.getenv("DEV_BOOTSTRAP_ADMIN_ENABLED", "false").strip().lower() == "true":
        resultados.append(
            Resultado("Admin de desenvolvimento", AVISO, "DEV_BOOTSTRAP_ADMIN_ENABLED=true: login local sem banco ativo.")
        )
    return resultados


def verificar_arquivos_da_interface() -> Resultado:
    from app_captacao.core.config.environment import get_static_path, get_template_path

    faltando = [caminho for caminho in (get_template_path(), get_static_path()) if not Path(caminho).is_dir()]
    if faltando:
        return Resultado("Interface", ERRO, f"Pastas da interface ausentes: {', '.join(faltando)}.")
    return Resultado("Interface", OK, "Templates e arquivos estaticos encontrados.")


def verificar_navegador() -> Resultado:
    from app_captacao.automacao import navegador
    from app_captacao.automacao.config import SELENIUM_BROWSER

    caminho = navegador.caminho_navegador(SELENIUM_BROWSER)
    if caminho:
        return Resultado("Navegador", OK, f"{SELENIUM_BROWSER} encontrado em {caminho}")
    return Resultado(
        "Navegador",
        AVISO,
        f"Navegador '{SELENIUM_BROWSER}' nao encontrado: o app abre, mas a automacao nao vai rodar.",
        "Instale o Microsoft Edge ou ajuste SELENIUM_BROWSER (edge ou chrome).",
    )


def verificar_pasta_de_downloads() -> Resultado:
    from app_captacao.automacao.config import DOWNLOAD_DIR

    pasta = Path(DOWNLOAD_DIR)
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        teste = pasta / f".teste_escrita_{os.getpid()}"
        teste.write_bytes(b"")
        teste.unlink()
    except OSError as exc:
        return Resultado(
            "Pasta de downloads",
            AVISO,
            f"Sem permissao de escrita em {pasta}: {exc.strerror or exc}.",
            "Ajuste SELENIUM_DOWNLOAD_DIR para uma pasta sua.",
        )
    return Resultado("Pasta de downloads", OK, str(pasta))


def verificar_banco() -> Resultado:
    from app_captacao.core.config.settings import USUARIO_TABLE
    from app_captacao.core.database.connection import get_db_connection

    servidor = os.getenv("DB_HOST", "").strip() or "(sem DB_HOST)"
    try:
        with closing(get_db_connection()) as conexao:
            cursor = conexao.cursor()
            cursor.execute(f"SELECT TOP 1 1 AS ok FROM {USUARIO_TABLE}")
            cursor.fetchone()
    except Exception as exc:
        detalhe = " ".join(str(exc).split())[:200] or type(exc).__name__
        return Resultado(
            "Banco de dados",
            ERRO,
            f"Nao foi possivel consultar {USUARIO_TABLE} em {servidor}: {detalhe}",
            "Confira a rede/VPN, o servidor, o nome do banco e o usuario SQL na configuracao.",
        )
    return Resultado("Banco de dados", OK, f"Conectado em {servidor}")


def executar_verificacoes(incluir_banco: bool = True) -> list[Resultado]:
    resultados = verificar_configuracao()
    if any(resultado.status == ERRO for resultado in resultados):
        return resultados
    resultados.append(verificar_arquivos_da_interface())
    resultados.append(verificar_navegador())
    resultados.append(verificar_pasta_de_downloads())
    if incluir_banco:
        resultados.append(verificar_banco())
    return resultados
