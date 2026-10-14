# Manual de Instalacao Segura

## Objetivo

Este fluxo foi preparado para distribuir o `AppCaptacao` sem instalador com privilegio de administrador e sem deixar o arquivo `.env` exposto para o usuario final.

O modelo adotado e:

- `AppCaptacao.exe` para executar a aplicacao
- `ConfigurarAppCaptacao.exe` para gravar a configuracao da maquina
- configuracao criptografada por usuario em `%LOCALAPPDATA%\AppCaptacao\app_captacao.env.enc`
- execucao local em `127.0.0.1`

## Arquivos para distribuir

Entregar apenas:

- `dist\AppCaptacao.exe`
- `dist\ConfigurarAppCaptacao.exe`
- este manual

Nao entregar junto:

- `.env`
- `app_captacao.env`
- `.env.enc`
- `app_captacao.env.enc` ao lado do executavel
- pasta `.config`
- codigo-fonte `.py`
- backups e pastas auxiliares do projeto

## Como gerar os executaveis

Na raiz do projeto:

```powershell
.\build_exe.ps1
```

Ou:

```bat
build_exe.bat
```

Ao final, os dois executaveis ficam na pasta `dist`.

## Fluxo recomendado de configuracao

1. Copie `AppCaptacao.exe` e `ConfigurarAppCaptacao.exe` para uma pasta do usuario.
2. Abra `ConfigurarAppCaptacao.exe`.
3. Importe um `.env` existente ou preencha os valores diretamente no editor.
4. Clique em `Gerar secret key` se desejar renovar a chave da sessao Flask.
5. Clique em `Salvar criptografado`.
6. Confirme que a mensagem de sucesso informou o caminho:

```text
%LOCALAPPDATA%\AppCaptacao\app_captacao.env.enc
```

7. Exclua qualquer `.env` em texto puro usado durante a configuracao.
8. Abra `AppCaptacao.exe`.

## Onde a configuracao fica salva

Arquivos principais:

- `%LOCALAPPDATA%\AppCaptacao\app_captacao.env.enc`
- `%LOCALAPPDATA%\AppCaptacao\state\`

Observacoes:

- o app prioriza a configuracao criptografada por usuario
- na versao empacotada, o carregamento de `.env` puro nao e o caminho padrao
- a senha digitada na tela principal nao fica mais salva no navegador

## O que foi endurecido neste fluxo

- a configuracao sensivel fica fora da pasta do executavel
- a configuracao e criptografada com DPAPI do Windows por usuario
- a senha de execucao nao retorna mais para a interface web
- a chave de sessao Flask nao usa mais um valor fixo inseguro por padrao
- o cache da sessao Sienge sai de `%TEMP%` e passa a usar armazenamento local do usuario

## O que excluir se necessario

Se for preciso remover a configuracao da maquina, use o proprio `ConfigurarAppCaptacao.exe` e clique em `Remover configuracao`.

Se precisar remover manualmente, excluir:

- `%LOCALAPPDATA%\AppCaptacao\app_captacao.env.enc`
- `%LOCALAPPDATA%\AppCaptacao\app_captacao.env`
- `%LOCALAPPDATA%\AppCaptacao\state\`
- qualquer `.env` ou `.env.enc` solto que tenha sido usado apenas na etapa de configuracao
- qualquer pasta `.config` criada ao lado do executavel em tentativas antigas

Se for preciso desinstalar a entrega portatil inteira, excluir tambem:

- a pasta onde ficou `AppCaptacao.exe`
- a pasta onde ficou `ConfigurarAppCaptacao.exe`
- a pasta de downloads da automacao, se desejado, por exemplo `Downloads\Automacao CAP`

## Checklist de entrega

- `AppCaptacao.exe` abre normalmente
- `ConfigurarAppCaptacao.exe` grava a configuracao em `%LOCALAPPDATA%`
- nao existe `.env` em texto puro na pasta entregue ao usuario
- a aplicacao abre em `http://127.0.0.1:4732/`
- a senha do campo de execucao nao volta preenchida apos recarregar a tela

## Observacao importante

Como o aplicativo roda no computador do proprio usuario, nao existe sigilo absoluto contra quem controla a maquina. O objetivo deste fluxo e reduzir bastante a exposicao acidental dos arquivos e impedir acesso trivial ao `.env` e a dados sensiveis no navegador.
