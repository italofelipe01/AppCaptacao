# Frontend: estrutura das telas e acessibilidade (fatia 2 da revisão)

Aprovada em 2026-10-16 ("continue", depois da fatia 1 em
[frontend-css-gerado.md](frontend-css-gerado.md)). Fica para as fatias seguintes: 3. textos e
acentos (inclusive os rótulos e mensagens citados aqui); 4. direção visual (paleta, foco, tabelas
em cartões abaixo de ~1100 px).

## Problema

Medido nas áreas úteis reais do Edge maximizado (1920×922, 1536×706, 1366×610, 1280×562) e em
1024, 960, 683 (1366 com zoom de 200%) e 390 px:

- **Execução:** o painel "Execução em andamento" e o resultado começam em y=1201, abaixo do
  formulário. Quem abre ou recarrega a tela durante uma execução vê só o formulário.
- **Menu:** o menu acompanha a altura da página e leva Tema e Sair para o fim dela (abaixo da
  área visível em todas as telas internas a partir de 1536). O estado recolhido é aplicado depois
  do carregamento, e o menu anima de aberto para recolhido a cada página.
- **Tabelas:** em Operações, os três botões de cada linha empilham até em 1920, e "Adicionar
  relatorios" quebra dentro do botão a partir de 1366. Em Usuários, a coluna Ações fica fora da
  área visível a partir de 1366 (1080 px de tabela para 931 visíveis).
- **Selos:** "5 baixado(s)" e "2 nao baixado(s)" quebram em duas linhas em todas as larguras. No
  Perfil, o e-mail sai do cartão em 1024.
- **Formulários:** rótulos sem `for` no login, na execução e nos filtros de Logs; "Valor padrão"
  sem nome acessível; o rótulo do combobox aponta para um campo oculto. Os campos de senha de
  Usuários e Perfil não têm `autocomplete`, e o Edge pode preencher a senha do administrador logado
  no cadastro de outro usuário.
- **Modais:** o foco do teclado não entra no modal nem volta ao fechar. Esc fecha todos os modais
  (e, na busca do combobox, o modal inteiro). Esc e clique fora descartam o que foi digitado sem
  aviso.
- **Leitor de tela:** o `aria-live` cobre o painel de andamento inteiro, que é refeito a cada
  1,2 s; mensagens de erro sem `role="alert"`; ícones do menu sem `aria-hidden`; a página ativa
  sem `aria-current`.

## Não objetivos

- Mudar textos, acentos, cores, paleta, foco visual ou o desenho das telas (fatias 3 e 4).
- Mudar rotas, endpoints ou nomes de campo de formulário (contrato do frontend). Os `id` novos
  não substituem nenhum `name`.
- Tabelas em telas estreitas (1024 px ou menos): continuam rolando para o lado até a fatia 4.

## Regras de comportamento

1. O menu lateral fica fixo na altura da janela; Tema e Sair ficam sempre visíveis. Se os itens não
   couberem, só a lista do meio rola.
2. O estado recolhido do menu é aplicado antes da primeira pintura, sem animação na troca de página.
   Com o menu recolhido, cada item mostra o nome como dica (`title`).
3. Na tela de execução, as mensagens, o andamento e o resultado, quando existem, vêm antes do
   formulário, nessa ordem.
4. Só o resumo do andamento é região `aria-live`, e ele só é reescrito quando o texto muda.
5. Os botões de ação das tabelas de Operações e Usuários ficam numa linha, sem quebrar o texto.
   Em 1280 px ou mais, a coluna Ações cabe sem rolar a tabela.
6. Selos de contagem e de status não quebram linha; textos longos sem espaço (e-mail, caminho)
   quebram dentro do próprio cartão.
7. Todo campo visível tem rótulo ligado (`for`/`id` ou `aria-labelledby`).
8. Senhas: `new-password` ao criar ou trocar senha, `current-password` na senha atual do Perfil. O
   login do usuário novo não recebe preenchimento automático.
9. Modais (`project/static/js/modal.js`, um só para Usuários e Operações):
   - ao abrir, o foco vai para o primeiro campo do corpo do modal; ao fechar, volta para quem
     abriu;
   - o Tab fica dentro do modal aberto;
   - Esc e clique fora fecham só o modal de cima e, se algo foi digitado, pedem confirmação antes
     de descartar;
   - cada modal tem `aria-labelledby` apontando para o título.
10. No combobox de relatório: Esc fecha só a lista e devolve o foco ao botão; setas navegam entre
    a busca e as opções; o botão informa `aria-expanded`.
11. Mensagens: erro com `role="alert"`, sucesso com `role="status"`. Um link "Ir para o conteúdo"
    aparece no primeiro Tab das telas internas.

## Casos de borda

- **Modal reaberto pelo backend com os valores do erro** (`modal_tipo=criar`): o estado inicial é
  o que veio preenchido, então fechar sem mexer não pede confirmação.
- **Modal de relatórios:** é montado por `fetch` antes de abrir. O estado inicial inclui os
  valores padrão já carregados.
- **Janela baixa (1280×562) com o menu aberto:** a lista do menu rola, e o cabeçalho e o rodapé
  ficam fixos.
- **Usuário de execução (perfil 3):** o menu tem dois itens, e nada muda.

## Riscos

- `position: sticky` no menu depende de nenhum ancestral com `overflow` diferente de `visible`.
  Conferido com prints rolando a página.
- A confirmação ao descartar pode incomodar quem usava Esc para limpar o formulário de propósito.
  Ela só aparece quando algo mudou.
- Com os botões numa linha, a coluna Nome fica mais estreita e quebra em mais linhas.

## Plano de teste

- `tests/web/test_estrutura_frontend.py` (renderiza as telas com os dublês):
  - os campos de senha têm o `autocomplete` certo;
  - todo `label` aponta para um campo que existe e todo campo visível tem rótulo;
  - o andamento e o resultado vêm antes do formulário;
  - o `aria-live` fica só no resumo;
  - os modais têm `aria-labelledby` válido, e as telas carregam `modal.js` sem redefinir
    `abrirModal`/`fecharModal`;
  - a página ativa tem `aria-current`;
  - os erros têm `role="alert"`.
- `node --check` em `modal.js` e `menu.js`.
- Revisão no navegador: as medidas acima, antes e depois, mais o teclado nos modais (foco,
  Tab, Esc com e sem alteração, Esc no combobox).

## Critérios de aceite

- Nas quatro áreas úteis de notebook e monitor: Sair visível sem rolar e rolando; andamento e
  resultado visíveis sem rolar; coluna Ações visível em Operações e Usuários; nenhum selo
  quebrado; nenhum botão de tabela com o texto quebrado.
- Os quatro gates do CLAUDE.md passam.

## Resultado (2026-10-16)

Implementado conforme [D20](../DECISIONS.md). Nas quatro áreas úteis:

- Sair ficou visível em todas as telas, sem rolar e rolando.
- Andamento e resultado começam em y=256, antes em y=1201.
- Os botões das tabelas ficam numa linha, antes um por linha.
- A coluna Ações aparece em Operações e Usuários a partir de 1280.
- Nenhum selo quebra.
- O e-mail do Perfil fica dentro do cartão.

No Edge, 28 verificações de teclado e foco passaram. A medição de contraste não mudou: esta fatia não
mexe em cor.

Ajustes feitos durante a conferência:

- **Menu baixo:** o menu aberto pedia 602 px, e em 1280×562 o último item ficava fora da lista.
  Janelas de até 700 px de altura usam menos respiro vertical no menu.
- **Respiro das tabelas:** abaixo de 1536 px, as células das tabelas de Operações e Usuários têm
  16 px de respiro lateral, e não 24.
- **Botão de Operações:** "Adicionar relatorios" virou "Relatórios". O botão abre o modal que
  lista, adiciona e remove os relatórios. Com o texto longo, a tabela passava 15 px da área de
  1280.
- **Mensagens da execução:** saíram de dentro do formulário. Depois do resultado anterior, um
  erro como "destino inválido" ficaria fora da tela.
- **Perfil:** só o e-mail quebra fora do espaço. Com a regra nos seis cartões, "Administrador"
  quebrava no meio em 1024.

Fica para a fatia 4: abaixo de 1280 as tabelas ainda rolam para o lado. Em 1280, o e-mail de
Usuários quebra em duas ou três linhas, porque os cabeçalhos em maiúsculas espaçadas ocupam a
largura.
