# Frontend: CSS gerado a partir dos templates (fatia 1 da revisão)

Aprovada em 2026-10-16 ("sim comece", após a revisão do frontend com as skills
web-design-guidelines e frontend-design). Fatias seguintes da revisão, fora desta spec:
2. menu fixo, andamento no topo, `autocomplete` das senhas, Esc no combobox, rótulos ligados aos
   campos; 3. textos e acentos; 4. direção visual.

## Problema

`project/static/css/tailwind-local.css` foi escrito à mão imitando o Tailwind. Das 365 classes que
os templates usam, 78 (21%) não existem nele e não fazem nada, sem aviso. Medido nas páginas
renderizadas (8 telas × 8 tamanhos × 2 temas):

- login com a metade direita do cartão vazia (`lg:flex`);
- indicador de "Execução em andamento" com 0×0 px;
- no tema escuro, item ativo e ícones do menu brancos, "Control Center" com contraste 1:1,
  números da tela Operações com 1,3:1;
- indicadores de Operações empilhados (`sm:grid-cols-3`); cartões de resultado sem a cor do
  status; selos de contagem em cápsulas verticais; caminho longo sem quebra.

Além disso, o reset não zera o fundo de `<button>`: botões sem classe de fundo mostram o cinza
padrão do Edge ("Tema claro" no login, tema no menu, "×" dos modais). E o logo azul-marinho
(`#243054`) fica com placa escura no tema escuro (cerca de 1,3:1), porque `app.css` redefine
`.bg-white` com especificidade maior que a variante `dark:`.

## Não objetivos

- Mudar layout, cores da paleta, textos ou estrutura das telas (fatias 2 a 4).
- Ligar o reset completo do Tailwind (preflight): zeraria margens de parágrafos e títulos e
  mudaria o espaçamento de todas as telas.
- Exigir Node ou internet para rodar o app: o CSS gerado é versionado.

## Regras de comportamento

1. `tailwind-local.css` é gerado pelo Tailwind v3.4.17 (executável standalone, sem Node) a partir
   de `project/templates/**/*.html` e `project/static/js/**/*.js`, com
   `scripts/css/tailwind.config.js` e `scripts/css/entrada.css`. Ninguém edita o arquivo à mão.
2. `scripts/gerar_css.ps1` baixa o executável na versão fixada para
   `%LOCALAPPDATA%\AppCaptacao\ferramentas\`, confere o SHA-256 publicado no release e gera o CSS.
   Sem internet, usa o executável já baixado.
3. O reset mantém o comportamento atual (box-sizing, margens do navegador em textos) e acrescenta
   só: borda `0 solid` como padrão (as classes `border-*` passam a funcionar como no Tailwind) e
   fundo transparente em `<button>`.
4. O logo fica sobre fundo branco nos dois temas.
5. Um teste falha quando uma classe usada num template (atributo `class`, `className` ou
   `classList` no JS) não tem regra no CSS gerado nem no `app.css`.

## Casos de borda

- Classe montada por concatenação no JS (`"bg-" + cor`): o Tailwind não acha; o teste também
  não. Os templates atuais não fazem isso; a regra é escrever a classe inteira.
- Opacidades fora da escala do v3 (`/12`, `/18`, `/88`) ficam declaradas na configuração.
- Classe que só serve de gancho para JS, sem estilo (`group`): lista explícita no teste.

## Riscos

- Classes que passam a existir mudam a tela de propósito (o login ganha a coluna da esquerda, os
  indicadores ficam lado a lado). Conferido com prints antes e depois.
- Pequenas diferenças de valor em relação ao arquivo feito à mão (sombra `shadow-lg`, desfoque de
  8 px em vez de 10 px, `text-rose-700` correto em vez do tom pink).

## Plano de teste

- `tests/web/test_css_gerado.py`: toda classe dos templates tem regra; o arquivo é o gerado (tem o
  cabeçalho do gerador); botões têm fundo transparente no reset; o logo tem a classe de placa.
- Contra o CSS antigo, o teste de classes falha listando as 78.
- Revisão visual com o mesmo roteiro da revisão (8 telas × 8 tamanhos × 2 temas), comparando
  contraste e layout antes e depois.

## Critérios de aceite

- Nenhuma classe dos templates sem regra; os quatro gates do CLAUDE.md passam.
- No tema escuro: menu sem fundos brancos, "Control Center" e números de Operações legíveis, logo
  visível. Botões sem o cinza do navegador.

## Resultado (2026-10-16)

Implementado conforme [D19](../DECISIONS.md). Classes sem regra: 75 → 0. Falhas de contraste
medidas no tema escuro: 33 → 10 (as restantes são textos secundários, fatia 3). No claro surgiram 5
em elementos que antes nem apareciam (numeração "01/02/03" do login, "Reutilizada somente enquanto
válida"), tratados nas fatias 2 e 4. Ajuste feito durante a conferência: o botão de tema do login
foi para o canto do cartão; sem isso o Entrar ficava 62 px abaixo da área visível num 1366×768.
