# AppCaptação — nova versão

A aplicação refatorada está na raiz deste diretório. A pasta `oldversion` permanece como referência da automação funcional e dos executores dedicados.

## Executar em desenvolvimento

```powershell
python .\run_app.py
```

Durante o desenvolvimento, a configuração é carregada de `oldversion/.env`. As credenciais não são copiadas para a nova árvore. No executável, permanece o fluxo de configuração criptografada definido em `app_core/app_config.py`.

## Fluxos principais

- **Relatório avulso:** executa um relatório com seus filtros dinâmicos.
- **Operação:** executa os relatórios vinculados na ordem de `IdCapRecursoRelatorioOperacao` e reutiliza a mesma sessão autenticada.
- **Acompanhamento:** consulta o trabalho em segundo plano e apresenta o estado individual de cada relatório.
- **Resultado:** considera sucesso somente após download estável, renomeação e confirmação no destino final.

## Testes locais

```powershell
python -m unittest discover -s tests -v
```

Os testes integrados com banco, Edge, Sienge e MFA devem ser executados manualmente no ambiente corporativo.
