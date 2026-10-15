# Downloads, nomes de arquivo e destino

Código em [automacao/downloads.py](../../src/app_captacao/automacao/downloads.py).

## Pasta de downloads

`SELENIUM_DOWNLOAD_DIR`; vazio usa `%USERPROFILE%\Downloads\Automação CAP`. O navegador é
configurado para baixar ali sem perguntar.

## Detecção do arquivo

1. Antes de exportar, o executor marca o início (`marcar_inicio_download`): guarda o horário e o
   tamanho/data de cada arquivo já existente.
2. Só conta como novo o arquivo criado ou alterado depois da marca. Arquivo antigo nunca é reaproveitado.
3. Enquanto existir `.crdownload`, `.tmp`, `.part` ou `.download` novo, o download está em
   andamento. Na espera entre relatórios, temporário parado há mais de
   `SELENIUM_DOWNLOAD_STALE_TEMP_SECONDS` (padrão 300 s) é tratado como download abandonado (de
   outra execução, por exemplo): vira aviso no log e não trava a pasta.
4. O arquivo precisa manter o mesmo tamanho (maior que zero) por `SELENIUM_DOWNLOAD_STABLE_CYCLES`
   verificações seguidas (padrão 3, a cada 0,75 s).
5. Limite total: `SELENIUM_DOWNLOAD_WAIT_TIMEOUT_SECONDS` (padrão 600 s). Sem arquivo novo, o
   relatório falha na etapa `download`.

## Nome do arquivo

`<nome do relatório>_<empresa>_<AAAA-MM-DD>.<extensão>`, com caracteres inválidos removidos. Se
o nome já existir, ganha `_2`, `_3`... nada é sobrescrito. Falha ao renomear vira etapa `renomeacao`.

## Destino final

- Sem destino informado na tela: o arquivo fica na pasta de downloads.
- Com destino: é copiado para `<destino>\Automação CAP\` (ou para o próprio destino, se a pasta
  já se chamar "Automação CAP"). A cópia é conferida pelo tamanho; falha vira etapa `copia`.
- O destino precisa ser **pasta local sincronizada do SharePoint/OneDrive ou caminho UNC**, com
  caminho completo (`C:\...` ou `\\servidor\...`). Link `http(s)://` do SharePoint e caminho
  relativo são recusados no `/processar`, antes de abrir o navegador
  (`downloads.mensagem_destino_invalido`).

## Relatórios paginados (Extrato saldo devedor presente, Quadro espelho)

A paginação é ajustada para 5000 linhas e cada página é exportada em Excel e renomeada na pasta
de downloads, sem ir para o destino. No fim de cada empresa, só o arquivo final vai para o
destino e para o resultado: a página única ou, com mais de uma página, o consolidado (a última
linha, totalizadora, de cada parte é descartada) e as páginas locais são apagadas. Se a
consolidação não gerar linhas, as páginas exportadas ficam como resultado.
