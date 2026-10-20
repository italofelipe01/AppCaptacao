# Execução de relatórios

Como um pedido feito na tela vira um arquivo baixado do Sienge. Fonte original:
`docs/originais/manual_de_utilizacao_v1.docx` e `docs/originais/roteiro_ia_superprompt.docx`,
revisados contra o código em 2026-10-14.

## Dois modos de execução

| Modo na tela | Campo `modo` | O que roda | Origem dos filtros |
| --- | --- | --- | --- |
| Relatório avulso | `completo` | Um relatório | Digitados na tela principal |
| Operação | `parceiros` | Todos os relatórios ativos da operação, na ordem de `IdCapRecursoRelatorioOperacao` | Salvos na operação, em Acompanhamento |

Nos dois casos o usuário informa o e-mail e a senha do Sienge (não são gravados) e,
opcionalmente, a pasta de destino (`sharepoint_link`).

## Passo a passo

1. **Validação** ([routes_execucao.py](../../src/app_captacao/web/routes_execucao.py)):
   e-mail e senha obrigatórios; destino vazio ou com caminho completo (pasta sincronizada ou
   UNC); filtros obrigatórios preenchidos
   ([regras.filtros_obrigatorios_sem_valor](../../src/app_captacao/catalogo/regras.py)).
2. **Job em segundo plano** ([execucao/jobs.py](../../src/app_captacao/execucao/jobs.py)):
   **uma automação por vez no computador**, qualquer que seja a sessão: o Edge da automação (porta
   de depuração) e a pasta de downloads são compartilhados. Com outra execução em andamento, o
   pedido é recusado com aviso. Cria o job com um item por relatório (`pendente`) e dispara uma thread
   ([execucao/runner.py](../../src/app_captacao/execucao/runner.py)). A tela consulta
   `/execucoes/atual` para mostrar o andamento.
3. **Navegador** ([automacao/navegador.py](../../src/app_captacao/automacao/navegador.py)):
   abre o Edge (ou Chrome, se `SELENIUM_BROWSER=chrome`). Não existe troca automática de navegador.
4. **Login no Sienge** ([automacao/login.py](../../src/app_captacao/automacao/login.py)): ver
   [login_sienge.md](login_sienge.md). Se o navegador ou o login falhar, todos os relatórios
   terminam como `ignorado` na etapa `autenticacao`, tanto no relatório avulso quanto na operação.
5. **Para cada relatório**, na mesma sessão autenticada
   ([automacao/execucao.py](../../src/app_captacao/automacao/execucao.py)):
   1. abre a `UrlRelatorio` cadastrada. Nas telas antigas (iframe `iFramePage`),
      `navegador.abrir_relatorio` espera o formulário do relatório ficar pronto (iframe novo,
      documento completo e campos na tela), até `SELENIUM_REPORT_READY_TIMEOUT_SECONDS` (60), e
      só então conta 6 s de folga para os scripts da tela (D26). As URLs só mudam depois do `#`: trocar de
      relatório não recarrega a página, e o iframe da tela anterior é marcado antes para nunca ser
      confundido com o novo. Mesma URL da tela atual (o Sienge reabre a última tela visitada):
      recarrega. As duas telas novas (MUI: Saldo devedor e Quadro espelho) seguem como antes;
   2. escolhe o executor dedicado (ver [relatorios_e_filtros.md](relatorios_e_filtros.md)). Os
      executores das telas antigas entram sempre no iframe do relatório (`iframe_do_relatorio`),
      nunca no de um widget da página (novidades, chat);
   3. o executor preenche os filtros, gera e exporta o relatório;
   4. o download é monitorado, renomeado e copiado (ver [downloads_e_destino.md](downloads_e_destino.md));
   5. o item vira `baixado` só com arquivo confirmado no destino; senão `nao_baixado`, com a etapa da falha.
6. **Entre relatórios**: espera a pasta de downloads estabilizar, sem pausa fixa depois (a próxima
   tela espera o próprio formulário). Depois do login, a folga é de 2 s
   (`SELENIUM_POST_LOGIN_WAIT_SECONDS`). Se a pasta não estabilizar após uma
   falha, os relatórios restantes viram `ignorado` para não associar o arquivo errado. Depois de
   uma falha, a automação volta para a aba do Sienge; se a sessão do Selenium caiu, reconecta ao
   Edge e refaz o login antes do próximo relatório (até 2 vezes; depois disso os restantes viram
   `ignorado` na etapa `autenticacao`).
   - **Na tela, durante a execução**, cada arquivo que chega ao destino aparece no relatório em
     andamento ("N arquivo(s) salvo(s); último: caminho"). No fim, cada relatório baixado diz
     quantos arquivos foram salvos e em qual pasta, e o resumo lista as pastas. Relatório que falha
     no meio (por exemplo na 3ª empresa) mostra os arquivos das empresas que já tinham sido salvos.
7. **Navegador no fim**: o Edge da automação é fechado, salvo com
   `SELENIUM_KEEP_BROWSER_OPEN=true`; quando a sessão cai no meio, o driver só é desconectado,
   porque o mesmo Edge é reanexado.
8. **Consolidação** ([consolidacao_de_relatorios.md](consolidacao_de_relatorios.md)): cada
   relatório `baixado` com layout conhecido ganha o consolidado na pasta dele, conferido com os
   totais do Sienge. Não muda o estado: o resultado entra na mensagem do relatório.
9. **Fim**: o job fica `concluida` com o resumo "N baixado(s); M não baixado(s)", mais quantos
   consolidados saíram. Com `APP_SAVE_LOGS=true`, o resultado vai para a tabela de log de operação.
10. **Falha inesperada no meio** (navegador derrubado, erro de programa): o que já terminou fica
   como estava; o relatório em andamento vira `nao_baixado` e os que não começaram viram
   `ignorado`, os dois na etapa `execucao`. A tela mostra uma mensagem genérica; o detalhe vai
   para o log técnico.

## Estados de cada relatório

| Estado | Significado |
| --- | --- |
| `pendente` | Aguardando a vez na fila da operação |
| `em_execucao` | Filtros sendo preenchidos ou download em andamento |
| `baixado` | Arquivo confirmado no destino final |
| `nao_baixado` | Falhou; `etapa` diz onde: `execucao`, `download`, `renomeacao`, `copia`, `preenchimento_modal` |
| `ignorado` | Não foi tentado: login falhou (`autenticacao`), a pasta de downloads ficou instável (`download`) ou a automação parou antes dele por falha inesperada (`execucao`) |

## Regras que não podem ser quebradas

- Sucesso só depois de arquivo estável, renomeado e confirmado no destino. Clique em "exportar" não é sucesso.
- Relatório sem executor dedicado é lacuna de cadastro: a execução falha com mensagem clara, nunca
  tenta cliques genéricos.
- Uma operação usa uma única sessão autenticada para todos os relatórios.
- A senha do Sienge nunca é gravada (nem em sessão, nem em log, nem em banco).
