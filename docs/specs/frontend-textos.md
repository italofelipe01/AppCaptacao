# Frontend: textos, acentos e contraste dos textos (fatia 3 da revisão)

Pedida em 2026-10-16 ("depois faça o Fatia 3 (textos)"), depois da fatia 2 em
[frontend-estrutura-acessibilidade.md](frontend-estrutura-acessibilidade.md). Fica para a fatia 4:
paleta, foco visual, rótulos em maiúsculas, decoração e tabelas em cartões.

## Problema

- **Acentos:** todas as telas misturam texto acentuado com "execucao", "relatorio", "Acoes",
  "Codigo", "Nivel", "Historico", inclusive nos títulos das abas e nas mensagens que vêm das rotas
  ("Usuario ou senha invalidos").
- **Textos que não correspondem ao sistema:**
  - **Execução:** "Sessão protegida, reutilizada somente enquanto válida", quando a sessão nunca
    é restaurada (D6) e o Edge fecha no fim (D17).
  - **Login:** "Entre com sua conta corporativa", mas o login é o usuário do AppCaptação, não a
    conta Microsoft.
  - **Logs:** a lista vazia promete registros "assim que o banco for conectado", quando a causa
    hoje é a gravação desligada (`APP_SAVE_LOGS=false`) ou um filtro sem resultado.
  - **Resultado:** "Diagnóstico detalhado" manda para Logs, que o perfil 3 nem acessa e que está
    sem gravação.
  - **Operações:** "Adicionar filtro" só mostra ou esconde a edição. "Operações ativas" conta a
    lista filtrada.
- **Nome do app:** varia entre "EBM Automacao" (aba), "Control Center" (menu) e "AppCaptação"
  (login).
- **Valores crus:** código no lugar do nome em área ("captacao"), evento ("login_falha"), tipo e
  status do log, e estado da execução ("nao baixado"). O placeholder mostra o identificador técnico
  do campo (`filter.cdEmpresaView`).
- **Contraste do texto:** medido nas 8 telas × 8 tamanhos × 2 temas, 28 textos abaixo do mínimo
  da WCAG AA no claro e 10 no escuro:
  - "EBM" em ciano no menu claro, com 1,36:1;
  - rótulos e marcadores em `slate-400` sobre branco, com 2,56:1;
  - selos em `slate-500` sobre `slate-100`, com 4,34:1;
  - no escuro, "R"/"OP", "Resultado da execucao", "Operações ativas" e o nome da operação no
    andamento.

## Não objetivos

- Mudar a paleta, os tamanhos de fonte, os rótulos em maiúsculas espaçadas ou o desenho (fatia 4).
- Reescrever as mensagens internas de cada executor do Sienge (`automacao/relatorios/executores/`).
  Elas são muitas e algumas descrevem a tela do Sienge. Entram só os resumos que aparecem no
  topo do resultado.
- Mudar rotas, endpoints, nomes de campo ou os valores gravados no banco (área, evento, status).
  Só o texto exibido muda.

## Regras de comportamento

1. **Português com acentos:** o texto visível nas telas, nos títulos das abas, nas mensagens das
   rotas e nas mensagens de regra de negócio que chegam à tela (catálogo, usuários, jobs) usa
   português com acentos.
2. **Nome do app:** é "AppCaptação" no menu, no login e nos títulos das abas
   (`<página> | AppCaptação`).
3. **Textos fiéis ao sistema:**
   - na execução, o quadro diz que o login é refeito a cada execução e que o Edge fecha no fim;
   - no login, pede o usuário e a senha do AppCaptação;
   - o resultado aponta o log técnico do computador;
   - a lista vazia de Logs diz se há filtro sem resultado ou se a gravação está desligada.
4. **Valores gravados:** códigos de área, evento, tipo, status e estado aparecem pelo nome, a
   partir de uma tabela única em `components/rotulos.html`. Os valores enviados ao backend não
   mudam.
5. **Botões dizem o que fazem:**
   - "Editar" em vez de "Edicao";
   - "Editar filtros" em vez de "Adicionar filtro";
   - "Remover" para tirar um relatório da operação, com a confirmação e a mensagem de sucesso
     usando o mesmo verbo.
6. **Contraste:** todo texto medido atinge a WCAG AA nos dois temas (4,5:1, ou 3:1 em texto
   grande), inclusive os placeholders.

## Casos de borda

- **Valor sem nome na tabela de rótulos** (área nova cadastrada direto no banco): aparece o valor
  cru, como hoje.
- **Perfil desconhecido:** "Usuário".
- **Logs:** com filtro e sem resultado, a mensagem fala do filtro, mesmo com a gravação desligada.

## Riscos

- Testes e rotinas que procuram texto exato de mensagem. Os testes são atualizados junto, e
  nenhum código de produção compara mensagem.
- Quem tem favorito com o título antigo da aba: só o nome muda.

## Plano de teste

- `tests/web/test_textos_frontend.py`:
  - as telas renderizadas não têm as palavras sem acento da lista (fora de `id`, `name`, `value` e
    código);
  - os títulos das abas terminam em "| AppCaptação";
  - a área, o evento e o perfil aparecem pelo nome;
  - a lista vazia de Logs distingue filtro e gravação desligada;
  - "Sessão protegida" e "conta corporativa" não aparecem mais.
- Testes existentes que conferem mensagens passam a conferir o texto novo, e os que conferiam
  ausência de mensagem continuam falhando contra o atalho.
- Revisão no navegador: a medição de contraste das 8 telas × 8 tamanhos × 2 temas sem nenhum
  texto abaixo do mínimo.

## Critérios de aceite

- Zero textos abaixo da WCAG AA na medição, nos dois temas.
- Nenhuma das palavras da lista sem acento nas telas renderizadas.
- Os quatro gates do CLAUDE.md passam.

## Resultado (2026-10-16)

Implementado conforme [D21](../DECISIONS.md).

- **Contraste:** falhas medidas de 28 para 0 no tema claro e de 10 para 0 no escuro. O "EBM" do
  menu passou a ciano 700 no claro.
- **Placeholders:** 4,76:1 no claro e 6,96:1 no escuro (antes, 2,6 e 3,7).
- **Teste:** os 5 testes de `test_textos_frontend.py` falham contra os templates da fatia 2.

Entraram também, por chegarem à tela:

- os detalhes da auditoria (coluna Detalhe dos Logs);
- os erros em JSON que a execução e Operações mostram;
- os eventos que o filtro de Logs não listava (usuário, senha e remoção de relatório).

As funções mortas `toggleAccordion` e `formatarDetalheFiltro` saíram de `main.html`. Os
registros antigos de log continuam com o texto gravado na época.
