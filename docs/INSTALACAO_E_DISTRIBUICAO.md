# Instalação e distribuição

Dois jeitos de rodar o AppCaptacao. Fonte original: `MANUAL_INSTALACAO_SEGURA.md` e
`INTRANET.md` da versão anterior (no histórico do git).

| | Código-fonte (desenvolvimento e uso interno) | Executável (usuário final) |
| --- | --- | --- |
| Como abre | `Iniciar AppCaptacao.bat` | `AppCaptacao.exe` |
| Precisa de Python | Sim (3.11+) | Não |
| Configuração | `.env` na raiz do repositório | `%LOCALAPPDATA%\AppCaptacao\app_captacao.env.enc` (cifrada) |
| Verifica o ambiente antes de abrir | Sim (checklist do `run.py`) | Não |

## Código-fonte

1. Instale o Python 3.11+ marcando **Add python.exe to PATH**.
2. Copie `.env.example` para `.env` e preencha os dados do banco e a `FLASK_SECRET_KEY`.
3. Dê duplo clique em `Iniciar AppCaptacao.bat`. Na primeira vez ele cria o `.venv` e instala as
   bibliotecas (precisa de internet). A janela mostra cada etapa e, no fim, com sucesso ou com
   erro, espera uma tecla para fechar.
4. (Opcional) `scripts\criar_atalho.bat` cria o atalho na Área de Trabalho.

### Levar para outro computador

- O `.bat` não usa caminho fixo: funciona em qualquer pasta, inclusive com espaços, acentos ou na
  rede (`\\servidor\...`).
- O `.venv` guarda o caminho do Python do computador que o criou. Se ele for copiado junto, o
  `.bat` detecta que não roda e recria com o Python do computador novo. O melhor é não copiá-lo.
- **Nunca** copie `.env`, `.config\` ou `*.env.enc` para outra pessoa: o `.env` tem a senha do
  banco em texto puro, e os `.enc` são cifrados com DPAPI para o usuário que os criou (não abrem
  em outro computador). Em cada computador, crie o `.env` a partir do `.env.example`.
- Prefira pastas com caminho curto (por exemplo `C:\AppCaptacao`): o Windows limita caminhos a 260
  caracteres e a instalação das bibliotecas pode falhar em pastas muito profundas.

O checklist pode ser rodado sem abrir o app:

```powershell
.\.venv\Scripts\python.exe run.py --somente-verificar
```

## Executáveis

Gerar (precisa do `.venv` criado):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\gerar_executaveis.ps1 -Limpar
```

Saída: `dist\AppCaptacao.exe` e `dist\ConfigurarAppCaptacao.exe`.

### Entregar ao usuário

Entregar **só** os dois `.exe` (e este documento, se útil). **Nunca** entregar `.env`,
`app_captacao.env`, `*.env.enc`, a pasta `.config`, código-fonte ou backups.

### Configurar na máquina do usuário

1. Abra `ConfigurarAppCaptacao.exe`.
2. Importe um `.env` ou preencha no editor; use **Gerar secret key** para uma chave nova.
3. Clique em **Salvar criptografado**. A mensagem confirma
   `%LOCALAPPDATA%\AppCaptacao\app_captacao.env.enc`.
4. Apague qualquer `.env` em texto puro usado na configuração.
5. Abra `AppCaptacao.exe` → **Iniciar servidor**. O navegador abre em `http://127.0.0.1:4732/`.

O arquivo `.enc` usa DPAPI: só funciona no mesmo usuário e na mesma máquina em que foi gerado.

### Onde ficam os dados do usuário

| Caminho | Conteúdo |
| --- | --- |
| `%LOCALAPPDATA%\AppCaptacao\app_captacao.env.enc` | Configuração cifrada |
| `%LOCALAPPDATA%\AppCaptacao\state\` | Perfil do Edge da automação e sessões Sienge salvas (cifradas) |
| `%LOCALAPPDATA%\AppCaptacao\logs\` | Log técnico |
| `Downloads\Automação CAP\<Relatório>\` | Relatórios baixados e o consolidado de cada um (padrão) |

Para remover a configuração: **Remover configuração** no configurador, ou apague os itens acima.

### Checklist de entrega

- `AppCaptacao.exe` abre e o servidor inicia.
- `ConfigurarAppCaptacao.exe` grava em `%LOCALAPPDATA%`.
- Nenhum `.env` em texto puro na pasta entregue.
- O app abre em `http://127.0.0.1:4732/` e o login funciona.
- Um relatório crítico é executado até `baixado`.

## Ordem de busca da configuração

Em desenvolvimento, o primeiro arquivo encontrado vence:

1. `.env` na raiz do repositório;
2. arquivos cifrados: `%LOCALAPPDATA%\AppCaptacao\app_captacao.env.enc`,
   `%LOCALAPPDATA%\AppCaptacaoData\...`, `.config\app_captacao.env.enc` ao lado do app;
3. arquivos em texto puro: `.config\app_captacao.env`, `app_captacao.env`, `.env` ao lado do app.

No executável, texto puro só é lido com `APP_CAPTACAO_ALLOW_PLAINTEXT_ENV=true`.
`APP_CAPTACAO_CONFIG_DIR` troca a pasta padrão. O arquivo de configuração vale sobre variável de
mesmo nome definida no ambiente do Windows (D25): uma `DB_USER` de outro projeto não troca a conta
do banco do AppCaptação. O checklist avisa quais variáveis do Windows foram ignoradas, só pelo nome.
