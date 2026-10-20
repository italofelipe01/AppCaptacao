# Changelog

<!-- markdownlint-disable MD012 MD024 -->

Todas as alterações notáveis deste projeto serão documentadas neste arquivo. As entradas são
geradas pelo `python-semantic-release` a partir dos commits (Conventional Commits).

<!-- version list -->

## v1.2.3 (2026-10-20)

### Performance Improvements

- **automacao**: Esperar a tela do relatorio e entrar sempre no iframe do formulario
  ([`ee8d9c3`](https://github.com/italofelipe01/AppCaptacao/commit/ee8d9c329e0f60af658e22be5eb891a113aa4950))


## v1.2.2 (2026-10-20)

### Bug Fixes

- **config**: Chave vazia no arquivo nao apaga variavel ja definida
  ([`c97c9fc`](https://github.com/italofelipe01/AppCaptacao/commit/c97c9fc75c85756e200e61514098f4fc5be0c6fb))


## v1.2.1 (2026-10-20)

### Bug Fixes

- **config**: Usar a configuracao do app mesmo com variaveis de outro projeto no Windows
  ([`6316ba7`](https://github.com/italofelipe01/AppCaptacao/commit/6316ba7f9f5d0d34454ee935a56e121cb8d50b97))


## v1.2.0 (2026-10-20)

### Features

- **automacao**: Conferir os filtros do app contra a tela do Sienge
  ([`b0c89ba`](https://github.com/italofelipe01/AppCaptacao/commit/b0c89bac2deb0799d79ac172d2c8f99a766a73b3))

- **consolidacao**: Registrar os filtros usados na aba Parametros do consolidado
  ([`28d617b`](https://github.com/italofelipe01/AppCaptacao/commit/28d617b1e3b42f41088e9943fe4602845415e147))


## v1.1.1 (2026-10-16)

### Bug Fixes

- **automacao**: Fechar a janela do relatorio so depois do download
  ([`f735f99`](https://github.com/italofelipe01/AppCaptacao/commit/f735f99281e79a84fdc2c1f2f4ea5f01cb3e1d49))


## v1.1.0 (2026-10-16)

### Bug Fixes

- **automacao**: Fechar o Edge anexado ao fim da execucao
  ([`1c684a4`](https://github.com/italofelipe01/AppCaptacao/commit/1c684a473150841c81669f23deaec109986719df))

- **web**: Gerar o CSS de utilitarios a partir dos templates
  ([`5302060`](https://github.com/italofelipe01/AppCaptacao/commit/5302060a3effb3820412ea1d6e302ab42cf617e9))

- **web**: Menu fixo, andamento no topo e modais pelo teclado
  ([`1f0df14`](https://github.com/italofelipe01/AppCaptacao/commit/1f0df148bc88e67a855f349bc47ebc06f852a18f))

- **web**: Textos com acento, fieis ao sistema e com contraste legivel
  ([`20d60a5`](https://github.com/italofelipe01/AppCaptacao/commit/20d60a5ee5bec04a9f2e2084fa93377361497c02))

### Chores

- Silenciar MD012 no changelog gerado
  ([`c63b79d`](https://github.com/italofelipe01/AppCaptacao/commit/c63b79df4bd4f83d60a197c11e7fdb93f364860f))

- **tools**: Corrigir os avisos de tipo do BaixaPDFs
  ([`aaf23e1`](https://github.com/italofelipe01/AppCaptacao/commit/aaf23e1291fe38fa8d20bd5bfd7b5dd8d0a7907a))

### Features

- **consolidacao**: Pasta por relatorio e consolidado conferido com o Sienge
  ([`2acd7b2`](https://github.com/italofelipe01/AppCaptacao/commit/2acd7b254d21e9ec3d7e17b81840e0e1d1030afb))


## v1.0.2 (2026-10-15)

### Bug Fixes

- **automacao**: Rodar a operacao em lote no Edge anexado sem perder a sessao
  ([`2c81618`](https://github.com/italofelipe01/AppCaptacao/commit/2c816186e2eabc72e9192963be7ed8335a6d5339))

- **log**: Uma linha por erro no console e sem mensagens duplicadas
  ([`092ea71`](https://github.com/italofelipe01/AppCaptacao/commit/092ea71e426d36e13a2bce5389d073c369a1bd86))


## v1.0.1 (2026-10-15)

### Bug Fixes

- **automacao**: Aceitar prazo fracionario na espera da pasta de downloads
  ([`e03aadd`](https://github.com/italofelipe01/AppCaptacao/commit/e03aaddf9fc43f533c0a904dc1b02239d9c32efb))

- **automacao**: Nao travar em temporario abandonado e copiar so o arquivo final dos paginados
  ([`b9e43db`](https://github.com/italofelipe01/AppCaptacao/commit/b9e43db781bf962c3268fbdbb5b6eca6e4f12f34))

- **catalogo**: Resolver o executor sem o ID do vinculo e centralizar o filtro fixo de Unidades
  ([`ece5881`](https://github.com/italofelipe01/AppCaptacao/commit/ece5881220d1f7de90b6648b0ad147a1e14cfde4))

- **config**: Conexao, checklist, senha e configurador coerentes
  ([`6b4dd60`](https://github.com/italofelipe01/AppCaptacao/commit/6b4dd602e4d10bf5ea590d2eba16cf10a1524ed7))

- **execucao**: Uma automacao por vez e estados corretos quando a execucao falha
  ([`49cff0d`](https://github.com/italofelipe01/AppCaptacao/commit/49cff0d84c684f3a0c75858ab88061908b2a49f8))

- **web**: Restringir a exportacao da aba administrativa de logs ao administrador
  ([`ad34be0`](https://github.com/italofelipe01/AppCaptacao/commit/ad34be07372613bb55af375a471f09c8272ee9e1))

### Continuous Integration

- Bump the github-actions group with 2 updates
  ([`69936f2`](https://github.com/italofelipe01/AppCaptacao/commit/69936f2a94faa5b2d8dcf0b690083dae59b781dc))

### Documentation

- Alinhar documentacao com o codigo revisado
  ([`79abe04`](https://github.com/italofelipe01/AppCaptacao/commit/79abe0413a0d7a01e782f1f57e28ca67656af2b9))


## v1.0.0 (2026-10-15)

- Initial Release
