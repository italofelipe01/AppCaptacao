"""CSS de utilitarios gerado a partir dos templates (docs/specs/frontend-css-gerado.md).

O arquivo antigo era escrito a mao e 21% das classes dos templates nao existiam nele: o
navegador ignorava a classe sem aviso (login com metade vazia, menu branco no tema escuro).
"""

import re
import unittest
from pathlib import Path

PROJETO = Path(__file__).resolve().parents[2] / "project"
TEMPLATES = PROJETO / "templates"
CSS_GERADO = PROJETO / "static" / "css" / "tailwind-local.css"
CSS_APP = PROJETO / "static" / "css" / "app.css"

# Classes que so marcam elementos para outras regras ou para o JS, sem estilo proprio.
SEM_REGRA_PROPRIA = {"group"}

_ATRIBUTO_CLASS = re.compile(r'class="([^"]*)"')
_CLASS_NAME = re.compile(r"\.className\s*=\s*([\"'`])(.*?)\1")
_CLASS_LIST = re.compile(r"classList\.(add|remove|toggle)\(([^)]*)\)")
_STRING = re.compile(r"[\"']([^\"']*)[\"']")
_JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\$\{[^}]*\}")


def classes_dos_templates() -> dict[str, str]:
    """Classe -> primeiro lugar em que aparece (arquivo:linha)."""
    encontradas: dict[str, str] = {}
    for template in sorted(TEMPLATES.rglob("*.html")):
        for numero, linha in enumerate(template.read_text(encoding="utf-8").splitlines(), start=1):
            local = f"{template.relative_to(PROJETO).as_posix()}:{numero}"
            valores = [m.group(1) for m in _ATRIBUTO_CLASS.finditer(linha)]
            valores += [m.group(2) for m in _CLASS_NAME.finditer(linha)]
            for metodo, argumentos in _CLASS_LIST.findall(linha):
                strings = _STRING.findall(argumentos)
                # toggle("classe", condicao): so o primeiro argumento e classe.
                valores += strings[:1] if metodo == "toggle" else strings
            for valor in valores:
                for classe in _JINJA.sub(" ", valor).split():
                    encontradas.setdefault(classe, local)
    return encontradas


# Escape de CSS: hexadecimal (".\32xl\:px-6" = "2xl:px-6", classe que comeca com digito) ou literal.
_ESCAPE_CSS = re.compile(r"\\([0-9a-fA-F]{1,6}) ?|\\(.)")


def _desescapar(nome: str) -> str:
    return _ESCAPE_CSS.sub(lambda m: chr(int(m.group(1), 16)) if m.group(1) else m.group(2), nome)


def classes_com_regra(*arquivos: Path) -> set[str]:
    css = "".join(arquivo.read_text(encoding="utf-8") for arquivo in arquivos)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    nomes = re.findall(r"\.((?:\\[0-9a-fA-F]{1,6} ?|\\.|[A-Za-z0-9_-])+)", css)
    return {_desescapar(nome) for nome in nomes}


class CssGeradoTests(unittest.TestCase):
    def test_toda_classe_dos_templates_tem_regra_no_css(self):
        definidas = classes_com_regra(CSS_GERADO, CSS_APP) | SEM_REGRA_PROPRIA
        faltando = {classe: local for classe, local in classes_dos_templates().items() if classe not in definidas}
        self.assertEqual(
            faltando,
            {},
            "Classe sem regra: rode scripts\\gerar_css.ps1 depois de mudar os templates.",
        )

    def test_css_de_utilitarios_e_o_gerado_e_nao_um_feito_a_mao(self):
        cabecalho = CSS_GERADO.read_text(encoding="utf-8")[:400]
        self.assertIn("Gerado por scripts/gerar_css.ps1", cabecalho)

    def test_botao_sem_classe_de_fundo_nao_herda_o_cinza_do_navegador(self):
        css = re.sub(r"\s+", " ", CSS_GERADO.read_text(encoding="utf-8"))
        self.assertRegex(css, r"button[^{]*\{[^}]*background-color: transparent")

    def test_logo_fica_sobre_fundo_branco_nos_dois_temas(self):
        # O logo e azul-marinho (#243054): sobre o fundo escuro o contraste cai para 1,3:1.
        css = CSS_APP.read_text(encoding="utf-8")
        self.assertRegex(css, r"\.logo-placa\s*\{[^}]*background-color:\s*#fff")
        for template in ("components/menu.html", "index.html", "main.html"):
            html = (TEMPLATES / template).read_text(encoding="utf-8")
            self.assertIn("logo-placa", html, template)


if __name__ == "__main__":
    unittest.main()
