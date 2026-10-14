# Specs

Feature nova ou mudança central começa por uma spec aqui (`docs/specs/<feature>.md`), aprovada
antes do código.

## Conteúdo mínimo

- **Problema** — o que dói hoje e para quem.
- **Não objetivos** — o que fica de fora.
- **Regras de comportamento** — numeradas, verificáveis.
- **Casos de borda** — banco fora do ar, Sienge mudou a tela, download incompleto, usuário sem permissão...
- **Riscos** — o que pode quebrar em produção.
- **Plano de teste** — quais testes falham contra o atalho.
- **Critérios de aceite** — como saber que terminou.

## Depois da aprovação

1. Design em texto listando os módulos alterados.
2. Implementação em fatias: domínio → serviço → rota/UI → testes.
3. Atualizar [ARCHITECTURE.md](../ARCHITECTURE.md), [projectmap.md](../projectmap.md) e
   [DECISIONS.md](../DECISIONS.md) se a responsabilidade entre módulos mudar.

## Specs

Nenhuma spec aberta.
