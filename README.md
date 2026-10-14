# AppCaptação

Automatiza o download de relatórios do **Sienge**. Você escolhe o relatório (ou um grupo de
relatórios), informa os filtros e o AppCaptação faz o resto: entra no Sienge, preenche a tela,
exporta, confere o arquivo e salva na pasta certa.

- [O que o app faz](#o-que-o-app-faz)
- [Primeiro uso, passo a passo](#primeiro-uso-passo-a-passo)
- [Criar o atalho na Área de Trabalho](#criar-o-atalho-na-área-de-trabalho)
- [Usando o app no dia a dia](#usando-o-app-no-dia-a-dia)
- [Quando algo dá errado](#quando-algo-dá-errado)
- [Como o projeto funciona](#como-o-projeto-funciona)
- [Para quem desenvolve](#para-quem-desenvolve)

## O que o app faz

```text
Você, no navegador            AppCaptação (no seu computador)              Sienge
──────────────────            ───────────────────────────────              ──────
Escolhe relatório     ──▶     Busca os filtros cadastrados no banco
e filtros                     Abre o Edge e faz login (Sienge ID + MFA) ──▶ Tela de login
                              Preenche os filtros do relatório         ──▶ Tela do relatório
                              Exporta e espera o arquivo terminar      ◀── Planilha
Vê o resultado        ◀──     Renomeia e copia para a pasta de destino
de cada relatório
```

- **Relatório avulso:** um relatório, com os filtros que você digita na hora.
- **Operação:** vários relatórios em sequência, com filtros já salvos, numa única sessão do Sienge.
- Cada relatório termina com um estado claro: **baixado**, **não baixado** (com a etapa da falha)
  ou **ignorado**.

## Primeiro uso, passo a passo

### 1. Confira o que você precisa

| Item | Para quê |
| --- | --- |
| Windows 10 ou 11 | O app usa recursos do Windows (criptografia DPAPI) |
| Microsoft Edge | É o navegador que a automação controla |
| Python 3.11 ou mais novo | Para rodar pelo código-fonte ([python.org](https://www.python.org/downloads/), marque **Add python.exe to PATH**) |
| Acesso à rede do SQL Server | Cadastro de usuários, relatórios e operações (use a VPN fora do escritório) |
| Conta no Sienge com MFA | Usada a cada execução; a senha não é gravada |

> Vai usar o executável (`AppCaptacao.exe`) em vez do código? Siga
> [Instalação e distribuição](docs/INSTALACAO_E_DISTRIBUICAO.md#executáveis): não precisa de Python.

### 2. Crie a configuração

Copie o modelo e preencha os dados do banco:

```powershell
Copy-Item .env.example .env
notepad .env
```

O mínimo para funcionar:

| Variável | O que colocar |
| --- | --- |
| `DB_HOST`, `DB_DATABASE`, `DB_USER`, `DB_PASSWORD` | Servidor, banco e usuário SQL do AppCaptação |
| `FLASK_SECRET_KEY` | Um texto longo e aleatório (o próprio `.env.example` mostra como gerar) |

O `.env` fica só no seu computador: ele nunca vai para o git.

### 3. Abra o app

Dê **duplo clique em `Iniciar AppCaptacao.bat`**. Na primeira vez ele prepara tudo sozinho (cria
o ambiente `.venv` e instala as bibliotecas, uns 2 minutos) e depois confere o ambiente:

```text
Verificando o ambiente do AppCaptacao...
  [ OK  ] Python: 3.13.2
  [ OK  ] Bibliotecas: 9 bibliotecas instaladas.
  [ OK  ] Configuracao: Carregada de C:\...\AppCaptacao\.env
  [ OK  ] Interface: Templates e arquivos estaticos encontrados.
  [ OK  ] Navegador: edge encontrado em C:\Program Files (x86)\Microsoft\Edge\...
  [ OK  ] Pasta de downloads: C:\Users\voce\Downloads\Automação CAP
  [ OK  ] Banco de dados: Conectado
Ambiente pronto.

AppCaptacao iniciando em http://127.0.0.1:4732/
```

O navegador abre sozinho na tela de login. **Deixe a janela preta aberta** enquanto usa o app;
fechá-la desliga o AppCaptação.

Se aparecer `[ERRO ]`, o app não abre e a linha seguinte diz o que corrigir. `[AVISO]` só informa.

## Criar o atalho na Área de Trabalho

**Jeito rápido:** dê duplo clique em `scripts\criar_atalho.bat`. Aparece o ícone **AppCaptacao**
(com o logo EBM) na sua Área de Trabalho, inclusive se ela for sincronizada pelo OneDrive.

**Jeito manual:**

1. Na pasta do projeto, clique com o botão direito em `Iniciar AppCaptacao.bat`.
2. **Mostrar mais opções** → **Enviar para** → **Área de trabalho (criar atalho)**.
3. Na Área de Trabalho, renomeie o atalho para `AppCaptacao`.
4. (Opcional) Botão direito no atalho → **Propriedades** → **Alterar ícone...** → **Procurar** e
   escolha `packaging\appcaptacao.ico` na pasta do projeto.

Depois é só dar duplo clique no atalho. Se o app já estiver aberto, o atalho só abre o navegador
nele, sem iniciar uma segunda cópia.

## Usando o app no dia a dia

### Telas

| Tela | O que faz | Quem acessa |
| --- | --- | --- |
| **Execução** (início) | Roda um relatório avulso ou uma operação e mostra o andamento de cada relatório | Todos |
| **Acompanhamento** | Cria operações, escolhe os relatórios e salva os filtros de cada um | Administrador e Cadastro de operação |
| **Usuários** | Cria, edita e inativa usuários do AppCaptação | Administrador |
| **Logs** | Histórico de execuções e de ações administrativas | Administrador e Cadastro de operação |
| **Perfil** | Seus dados e troca da sua senha | Todos |

### Rodando um relatório

1. Em **Execução**, informe o e-mail e a senha do **Sienge** (a senha não fica gravada).
2. (Opcional) Informe a pasta de destino: uma pasta sincronizada do SharePoint/OneDrive ou um
   caminho de rede (`\\servidor\pasta`). Link `https://` do SharePoint não funciona.
3. Escolha **Relatório avulso** (e preencha os filtros) ou **Operação**.
4. Clique para executar. Se o Sienge pedir o código do MFA, aprove no celular.
5. Acompanhe na própria tela: cada relatório passa para **baixado** ou **não baixado**.

### Onde ficam os arquivos

- Pasta de downloads: `Downloads\Automação CAP` (ou a definida em `SELENIUM_DOWNLOAD_DIR`).
- Nome: `<relatório>_<empresa>_<data>.xlsx`. Arquivo com o mesmo nome nunca é sobrescrito.
- Com destino informado, uma cópia vai para `<destino>\Automação CAP\`.

## Quando algo dá errado

| O que aparece | O que fazer |
| --- | --- |
| `[ERRO ] Bibliotecas` | Abra sempre pelo `Iniciar AppCaptacao.bat`; confira a internet/proxy na primeira vez |
| `[ERRO ] ... Login failed` no banco | Usuário ou senha SQL do `.env` incorretos ou expirados |
| `[ERRO ] ... timeout` no banco | Rede/VPN desligada ou `DB_HOST` errado |
| Relatório **não baixado** na etapa `download` | O Sienge não gerou o arquivo a tempo; tente de novo ou aumente `SELENIUM_DOWNLOAD_WAIT_TIMEOUT_SECONDS` |
| Etapa `copia` | O destino precisa ser pasta sincronizada ou caminho de rede |
| Todos **ignorados** na etapa `autenticacao` | Login no Sienge não concluiu: confira a senha e aprove o MFA a tempo |

Detalhes técnicos de cada falha ficam no log:
`%LOCALAPPDATA%\AppCaptacao\logs\appcaptacao.log`. Lista completa em
[Logs e erros](docs/LOGS_E_ERROS.md).

## Como o projeto funciona

O AppCaptação é um servidor web pequeno que roda **no seu computador** (`127.0.0.1:4732`). A
interface é aberta no navegador e conversa com cinco partes:

| Parte | Pasta | Papel |
| --- | --- | --- |
| Interface | `project/` | Telas HTML, CSS e JavaScript |
| Web | `src/app_captacao/web/` | Recebe os cliques da tela e chama as outras partes |
| Catálogo | `src/app_captacao/catalogo/` | Lê no SQL Server os relatórios, filtros e operações e decide qual "executor" atende cada relatório |
| Automação | `src/app_captacao/automacao/` | Controla o Edge com Selenium: login, executor de cada relatório, download |
| Base | `src/app_captacao/core/` | Configuração, conexão com o banco, login no app, usuários e logs |

Cada relatório do Sienge tem um **executor dedicado** em
`src/app_captacao/automacao/relatorios/executores/`, porque cada tela do Sienge tem seu jeito.
O passo a passo completo está em [docs/processos/](docs/processos/README.md).

## Para quem desenvolve

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # pytest e pyinstaller
.\.venv\Scripts\python.exe -m pytest                                # testes (sem rede/banco)
npx pyright@1.1.414 --pythonpath .venv\Scripts\python.exe           # tipos
.\.venv\Scripts\python.exe run.py --somente-verificar               # só o checklist
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\gerar_executaveis.ps1 -Limpar
```

- Estrutura e onde mudar cada coisa: [docs/projectmap.md](docs/projectmap.md).
- Regras para pessoas e agentes de IA: [docs/AI_CONTRACT.md](docs/AI_CONTRACT.md) e [CLAUDE.md](CLAUDE.md).
- Decisões: [docs/DECISIONS.md](docs/DECISIONS.md).
- Commits em Conventional Commits, em português e sem acento no assunto
  (`feat(automacao): ...`, `fix(web): ...`). A versão e o `CHANGELOG.md` são gerados pelo
  workflow de release.
- `tools/baixa_pdfs/` é uma ferramenta independente; não faz parte do app.
