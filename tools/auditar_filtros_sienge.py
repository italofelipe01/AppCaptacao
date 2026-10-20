"""Audita os filtros do app contra a tela de cada relatorio no Sienge (so leitura).

Uso, na raiz do repositorio:
    .\\.venv\\Scripts\\python.exe tools\\auditar_filtros_sienge.py --email voce@empresa.com.br

A senha vem de SIENGE_SENHA ou e pedida no terminal (vazio: login na janela do Edge).
O resultado vai para docs/auditoria-filtros-sienge.md. Detalhes em
src/app_captacao/automacao/auditoria_filtros.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app_captacao.automacao.auditoria_filtros import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
