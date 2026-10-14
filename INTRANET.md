# Publicacao na intranet

## Servidor

1. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

2. Inicie a aplicacao:

```powershell
python -m waitress --host=0.0.0.0 --port=4732 app:app
```

O servidor ficara disponivel em:

```text
http://172.16.20.5:4732
```

## Executavel Windows

### Build

1. Instale as dependencias do projeto:

```powershell
pip install -r requirements.txt
```

2. Gere os executaveis:

```powershell
.\build_exe.ps1 -WithConfigInstaller
```

Arquivos gerados:

- `dist\AppCaptacao.exe`
- `dist\InstalarConfiguracaoAppCaptacao.exe`

Se precisar gerar somente o aplicativo, sem o instalador de configuracao:

```powershell
.\build_exe.ps1
```

### Pacote de entrega

Ao compactar ou copiar para outra maquina, entregue apenas:

- `AppCaptacao.exe`
- `InstalarConfiguracaoAppCaptacao.exe`

Nao inclua:

- `.env`
- `.env.enc`
- `app_captacao.env`
- `app_captacao.env.enc`
- `.config\`

Se voce optar por gerar arquivos `.enc`, eles usam DPAPI do Windows e so funcionam no mesmo usuario/maquina onde foram gerados. Um `.enc` criado na maquina do desenvolvedor nao deve ser distribuido para outro usuario.

### Instalacao da configuracao

Na maquina do usuario, execute primeiro o instalador de configuracao:

```powershell
.\InstalarConfiguracaoAppCaptacao.exe --interactive
```

O assistente pergunta as variaveis no terminal e grava diretamente em:

```text
%LOCALAPPDATA%\AppCaptacao\app_captacao.env
```

Depois abra:

```powershell
.\AppCaptacao.exe
```

Opcao para ambiente de desenvolvimento, usando Python:

```powershell
python setup_local_config.py --interactive
```

Se voce recebeu um `.env` temporario na maquina do usuario, instale e apague o arquivo em seguida:

```powershell
python setup_local_config.py --source .env --delete-source
```

O arquivo sera gravado em `%LOCALAPPDATA%\AppCaptacao\app_captacao.env` com atributo oculto.
Se esse caminho estiver bloqueado na maquina, o instalador cai automaticamente para `%LOCALAPPDATA%\AppCaptacaoData`.

Se precisar instalar com criptografia por algum motivo, use:

```powershell
python setup_local_config.py --source .env --encrypt
```

### Execucao

Ao abrir o `AppCaptacao.exe`, a aplicacao inicia o servidor local e abre o Google Chrome automaticamente assim que o sistema estiver pronto.
Se o Chrome nao estiver instalado ou nao for localizado, a aplicacao usa o navegador padrao do Windows.

Por padrao, o destino final sera `http://127.0.0.1:4732/`.

Se quiser abrir uma rota especifica, configure a variavel:

```text
APP_LAUNCH_URL=/painel
```

Tambem aceita URL completa:

```text
APP_LAUNCH_URL=http://127.0.0.1:4732/login
```

### Solucao de problemas

Se aparecer erro de configuracao, remova configuracoes antigas e rode novamente o instalador:

```powershell
Remove-Item "$env:LOCALAPPDATA\AppCaptacao\app_captacao.env" -ErrorAction SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\AppCaptacao\app_captacao.env.enc" -ErrorAction SilentlyContinue
.\InstalarConfiguracaoAppCaptacao.exe --interactive
```

Nao copie arquivos de configuracao de outra maquina. Gere sempre localmente no usuario que vai executar o aplicativo.

## Script de autenticacao Sienge

Para abrir o Chrome e executar somente o login/autenticacao no Sienge:

```powershell
python .\login_sienge.py --email seuemail@empresa.com --senha suasenha
```

Para fechar o navegador automaticamente apos autenticar:

```powershell
python .\login_sienge.py --email seuemail@empresa.com --senha suasenha --fechar
```

Observacao: ocultar o arquivo ajuda a nao expor a configuracao no diretorio do programa. Se precisar de protecao adicional, use `--encrypt` ou um cofre de segredos.
