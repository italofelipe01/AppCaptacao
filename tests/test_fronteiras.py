"""Fronteiras entre camadas descritas em docs/ARCHITECTURE.md, verificadas nos imports."""

import ast
import re
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "app_captacao"


def _imports(pasta: str) -> dict[str, set[str]]:
    encontrados: dict[str, set[str]] = {}
    for arquivo in (SRC / pasta).rglob("*.py"):
        modulos = set()
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if isinstance(no, ast.ImportFrom) and no.module:
                modulos.add(no.module)
            elif isinstance(no, ast.Import):
                modulos.update(alias.name for alias in no.names)
        encontrados[str(arquivo.relative_to(SRC))] = modulos
    return encontrados


def _violacoes(pasta: str, proibidos: tuple[str, ...]) -> list[str]:
    return [
        f"{arquivo} importa {modulo}"
        for arquivo, modulos in _imports(pasta).items()
        for modulo in modulos
        if modulo.startswith(tuple(f"app_captacao.{p}" for p in proibidos))
    ]


class FronteirasTests(unittest.TestCase):
    def test_core_nao_depende_das_camadas_de_cima(self):
        self.assertEqual(
            _violacoes("core", ("catalogo", "automacao", "consolidacao", "execucao", "web", "app")), []
        )

    def test_consolidacao_so_depende_do_core(self):
        # Recebe o executor e os caminhos dos arquivos: nada de driver, catalogo ou job.
        self.assertEqual(_violacoes("consolidacao", ("catalogo", "automacao", "execucao", "web", "app")), [])

    def test_catalogo_nao_depende_de_automacao_execucao_ou_web(self):
        self.assertEqual(_violacoes("catalogo", ("automacao", "execucao", "web", "app")), [])

    def test_automacao_nao_depende_de_execucao_ou_web(self):
        self.assertEqual(_violacoes("automacao", ("execucao", "web", "app")), [])

    def test_persistencia_nao_le_o_contexto_do_flask(self):
        problemas = [
            arquivo
            for pasta in ("core/persistence", "catalogo")
            for arquivo, modulos in _imports(pasta).items()
            if "flask" in modulos
        ]
        self.assertEqual(problemas, [])

    def test_rotas_nao_escrevem_sql(self):
        sql = re.compile(r"\b(SELECT|INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM)\b")
        problemas = [
            arquivo.name
            for arquivo in (SRC / "web").glob("*.py")
            if sql.search(arquivo.read_text(encoding="utf-8"))
        ]
        self.assertEqual(problemas, [])

    def test_variaveis_de_ambiente_sao_lidas_depois_do_env(self):
        # Modulos que leem os.getenv no import precisam importar settings ou automacao.config antes.
        problemas = []
        permitidos = {"core/config/environment.py", "core/config/settings.py", "automacao/config.py"}
        for arquivo in SRC.rglob("*.py"):
            relativo = arquivo.relative_to(SRC).as_posix()
            if relativo in permitidos or relativo.startswith(("desktop/", "inicializacao/")):
                continue
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            for no in arvore.body:
                if isinstance(no, (ast.Assign, ast.AnnAssign)) and "getenv" in ast.unparse(no):
                    problemas.append(f"{relativo}:{no.lineno}")
        self.assertEqual(problemas, [])


if __name__ == "__main__":
    unittest.main()
