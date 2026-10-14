# Documentos originais (.docx)

Arquivos de referência histórica. **A fonte de verdade é o Markdown em `docs/`**, conferido
contra o código; os `.docx` não são mais atualizados.

| Arquivo | Origem | Conteúdo atualizado em |
| --- | --- | --- |
| `manual_de_utilizacao_v1.docx` | `Manual_AppCaptação.docx` (abril/2026) | [README.md](../../README.md), [INSTALACAO_E_DISTRIBUICAO.md](../INSTALACAO_E_DISTRIBUICAO.md), [processos/](../processos/) |
| `roteiro_ia_superprompt.docx` | `Roteiro_IA_AppCaptacao_SuperPrompt.docx` | [AI_CONTRACT.md](../AI_CONTRACT.md), [processos/](../processos/), [CLAUDE.md](../../CLAUDE.md) |

O "Termo de Entrega de Projeto - Executiva" e o "Esboço de Documentação" ficaram só no histórico
do git (commits `chore(legado)`); o conteúdo está em [projeto/visao_geral.md](../projeto/visao_geral.md).

## Onde os originais divergem do código atual

| Original dizia | O código atual faz |
| --- | --- |
| Google Chrome e chromedriver no PATH | Edge por padrão; Selenium Manager baixa o driver. Chrome só com `SELENIUM_BROWSER=chrome` |
| Edge com fallback para Chrome | Não há fallback: falha do Edge é falha (teste protege) |
| Restaurar cookies e storage da sessão salva | A sessão é salva, mas o login é sempre automático |
| Autenticação Playwright para login isolado | Módulo removido; login só por Selenium |
| Python 3.8+, Windows ou Linux | Python 3.11+, só Windows (DPAPI, pywin32) |
| `SELENIUM_DOWNLOAD_WAIT_TIMEOUT_SECONDS` padrão 30 | Padrão 600 |
| `APP_HOST` padrão 0.0.0.0 | Padrão 127.0.0.1 (0.0.0.0 expõe o app na rede) |
| "Execução agendada de relatórios" | Não há agendamento: a execução é disparada pelo usuário |
| Perfil (Admin) | A tela Perfil é de qualquer usuário (troca da própria senha) |
| Credenciais `execucao_email`/`execucao_senha` | E-mail e senha do Sienge digitados a cada execução, nunca gravados |
