"""Scripts embutidos nos templates: JS valido depois de renderizado e sem Jinja no codigo.

Jinja dentro de <script> (ex.: const x = {{ valor|tojson }};) funciona no navegador,
mas o editor acusa erro de sintaxe. Valores do backend chegam ao JS por blocos
<script type="application/json"> lidos com JSON.parse.
"""

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_captacao.app import app
from app_captacao.catalogo import operacoes, relatorios
from app_captacao.core.persistence import usuarios

TEMPLATES = Path(__file__).resolve().parents[2] / "project" / "templates"
SCRIPT = re.compile(r"<script(?P<attrs>[^>]*)>(?P<corpo>.*?)</script>", re.S)
ADMIN = {"id": 10, "login": "admin", "email": "a@example.com", "area": "ti", "access_id": 1, "ativo": 1, "data_criacao": None}


def _scripts(html):
    for match in SCRIPT.finditer(html):
        if "src=" in match.group("attrs"):
            continue
        yield match.group("attrs"), match.group("corpo")


class TemplatesJsTests(unittest.TestCase):
    def test_codigo_js_dos_templates_nao_mistura_jinja_fora_de_strings(self):
        problemas = []
        for template in TEMPLATES.rglob("*.html"):
            for attrs, corpo in _scripts(template.read_text(encoding="utf-8")):
                if "application/json" in attrs:
                    continue
                for linha in corpo.splitlines():
                    sem_strings = re.sub(r"(\"[^\"]*\"|'[^']*'|`[^`]*`)", "", linha)
                    if "{{" in sem_strings or "{%" in sem_strings:
                        problemas.append(f"{template.name}: {linha.strip()}")
        self.assertEqual(problemas, [])

    def _renderizar(self):
        app.config.update(TESTING=True, SECRET_KEY="test")
        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 10
            session["user_login"] = "admin"
            session["user_access_id"] = 1
        paginas = {}
        with patch.object(usuarios, "load_user_by_id", return_value=ADMIN), patch.object(
            usuarios, "load_usuarios", return_value=[]
        ), patch.object(operacoes, "load_operacoes", return_value=[]), patch.object(
            operacoes, "load_operation_report_summaries", return_value={3: [{"id": 7, "nome": "Extrato </script> 'x'"}]}
        ), patch.object(relatorios, "load_relatorios_disponiveis", return_value=[]):
            for rota in [
                "/main",
                "/usuarios?modal_tipo=editar&modal_usuario_id=4&modal_usuario_login=o%27neil",
                "/acompanhamento?modal_tipo=relatorios&modal_operacao_id=3&modal_operacao_nome=Fech%22amento",
                "/logs",
                "/perfil",
            ]:
                paginas[rota] = client.get(rota).get_data(as_text=True)
        return paginas

    def test_blocos_json_entregam_os_valores_do_backend(self):
        paginas = self._renderizar()
        dados = {}
        for rota, html in paginas.items():
            for attrs, corpo in _scripts(html):
                if "application/json" in attrs:
                    dados[rota.split("?")[0]] = json.loads(corpo)
        self.assertEqual(dados["/usuarios"]["modal_usuario_login"], "o'neil")
        self.assertEqual(dados["/acompanhamento"]["modal_operacao_nome"], 'Fech"amento')
        self.assertEqual(dados["/main"]["operacao_relatorios"]["3"][0]["nome"], "Extrato </script> 'x'")

    @unittest.skipUnless(shutil.which("node"), "Node.js nao instalado")
    def test_scripts_renderizados_sao_javascript_valido(self):
        paginas = self._renderizar()
        with tempfile.TemporaryDirectory() as tmp:
            for indice, (rota, html) in enumerate(paginas.items()):
                for ordem, (attrs, corpo) in enumerate(_scripts(html)):
                    if "application/json" in attrs:
                        continue
                    arquivo = Path(tmp) / f"script_{indice}_{ordem}.js"
                    arquivo.write_text(corpo, encoding="utf-8")
                    resultado = subprocess.run(["node", "--check", str(arquivo)], capture_output=True, text=True)
                    self.assertEqual(resultado.returncode, 0, f"{rota}: {resultado.stderr}")


if __name__ == "__main__":
    unittest.main()
