# BaixaPDFs

Ferramenta independente, anterior ao AppCaptacao, que baixa em lote os PDFs da página
`common/page/376` do Sienge para uma lista de empresas lida de uma planilha Excel.

Ela **não faz parte do app**: não é importada por `src/`, não é empacotada no executável e não
passa pelos testes. Fica no repositório porque o fluxo de login dela (Sienge ID + SSO Microsoft)
foi a referência copiada para `src/app_captacao/automacao/login.py`.

## Como usar

```powershell
python tools\baixa_pdfs\BaixaPDFs.py
```

Na primeira execução o script instala sozinho `selenium`, `requests`, `pillow`,
`webdriver-manager`, `pandas` e `openpyxl` no Python que o executou. Rode-o em um ambiente
separado se não quiser essas bibliotecas no Python do sistema.

O log técnico vai para `execucao_debug.log` na pasta de onde o script foi chamado.
