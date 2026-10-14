# Visão geral do projeto

Consolida o "Termo de Entrega de Projeto - Executiva" e o "Esboço de Documentação" das versões
anteriores (preservados no histórico do git, commits `chore(legado)`).

## Problema

A captação e a execução de relatórios no Sienge exigiam muitas interações manuais: acessar o
sistema, escolher o relatório, preencher filtros, exportar, consolidar planilhas e organizar os
arquivos no destino compartilhado. Era um trabalho repetitivo, demorado, sujeito a erro e difícil
de padronizar entre relatórios e empresas.

## Objetivo

Automatizar a execução de relatórios no Sienge em uma interface única — login, escolha de
relatório ou operação, filtros, download, consolidação e cópia para o destino — reduzindo o tempo
operacional, padronizando a rotina e liberando a equipe para análise.

## Público

- Equipes que extraem relatórios operacionais e financeiros do Sienge com filtros por empresa,
  período, empreendimento ou centro de custo.
- Lideranças que precisam de previsibilidade e rastreabilidade na geração dos arquivos.

## Solução

Aplicação Python executada na máquina do usuário:

- **Interface web local** (Flask + Waitress em `http://127.0.0.1:4732`) para login, execução,
  cadastro de operações, usuários e logs.
- **Automação de navegador** (Selenium + Edge) com login Sienge ID + Microsoft e executores
  dedicados por relatório.
- **Catálogo no SQL Server**: relatórios, filtros e operações parametrizam a automação.
- **Downloads controlados**: arquivo estável, nome padronizado e cópia para pasta sincronizada.
- **Distribuição Windows**: `AppCaptacao.exe` + `ConfigurarAppCaptacao.exe` (configuração
  criptografada por usuário), ou execução pelo código-fonte com `Iniciar AppCaptacao.bat`.

## Benefícios registrados na entrega

| Indicador | Antes | Depois |
| --- | --- | --- |
| Esforço humano | Execução manual e repetitiva | Usuário só aciona e acompanha |
| Padronização | Dependia de cada operador | Fluxo automatizado com etapas definidas |
| Confiabilidade | Risco de erro por volume e repetição | Preenchimento, exportação e consolidação automáticos |
| Escalabilidade | Limitada à disponibilidade da equipe | Várias empresas, relatórios e páginas por execução |
| Segurança | Arquivos de configuração visíveis | Configuração por usuário, cifrada com DPAPI |

A entrega liberou uma pessoa da operação para outras demandas, sem aumento de quadro.

## Manutenção contínua

- Mudanças de tela do Sienge (IDs de componentes MUI variam) exigem ajuste no executor afetado.
- Conexão lenta aumenta o tempo de download; arquivos temporários nunca contam como finais.
- Configuração cifrada não pode ser copiada entre máquinas ou usuários.
- Depois de mudar o código: rodar os testes, gerar os executáveis e testar um relatório crítico.
