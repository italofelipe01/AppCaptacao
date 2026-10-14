# Publicacao na intranet

## App desktop

O projeto atual e distribuido como aplicativo desktop com configurador separado para a gravacao segura da configuracao no perfil do usuario.

### Build

1. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

2. Gere os executaveis:

```powershell
.\build_exe.ps1
```

Arquivos gerados:

- `dist\AppCaptacao.exe`
- `dist\ConfigurarAppCaptacao.exe`

### Pacote de entrega

Ao compactar ou copiar para outra maquina, entregue apenas:

- `AppCaptacao.exe`
- `ConfigurarAppCaptacao.exe`

Nao inclua:

- `.env`
- `.env.enc`
- `app_captacao.env`
- `app_captacao.env.enc`
- `.config\`

### Configuracao

1. Abra `ConfigurarAppCaptacao.exe`.
2. Importe um `.env` ou preencha os valores diretamente no editor.
3. Clique em `Salvar criptografado`.
4. Exclua qualquer `.env` em texto puro usado durante a configuracao.

O aplicativo principal prioriza a configuracao criptografada do usuario em:

- `%LOCALAPPDATA%\AppCaptacao\app_captacao.env.enc`

Os arquivos `.enc` usam DPAPI do Windows e so funcionam no mesmo usuario e maquina onde foram gerados.

### Execucao

Abra o `AppCaptacao.exe`.

## Script de autenticacao Sienge

Para abrir o Chrome e executar somente o login/autenticacao no Sienge:

```powershell
python .\scripts\login_sienge.py --email seuemail@empresa.com --senha suasenha
```

Para fechar o navegador automaticamente apos autenticar:

```powershell
python .\scripts\login_sienge.py --email seuemail@empresa.com --senha suasenha --fechar
```
