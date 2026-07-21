# Sittax Context Handoff

Data de referencia: 2026-07-20

## Estado atual consolidado

- O host `apuracao.sittax.com.br` aceita `empresaCnpj + periodo` e retorna apuracao valida.
- O host `api.sittax.com.br` exige sessao HTTP stateful com `cookie jar` persistido.
- O host `api.sittax.com.br` nao se comporta como API stateless pura.
- Sucesso da apuracao isolada nao basta para chamadas contextuais no host `api`.
- `Authorization: Bearer ...` isolado nao basta para `painelprincipal`, DIFAL e documentos.
- Montar manualmente um header `Cookie` em chamada avulsa tambem nao bastou no replay stateless.
- O replay stateful com sessao persistente, cookie jar e afinidade confirmou handoff funcional em 2026-07-20.
- A implementacao atual do Lumen, baseada em cliente stateful por sessao, esta alinhada com a evidencia final.

## Resultado final observado em 2026-07-20

### O que falhou

Falhou o replay manual simplificado com:

- `Authorization: Bearer ...`
- cookies montados manualmente no header
- sem `WebRequestSession`
- sem reaproveitamento automatico do `cookie jar`

Nesse modo, o portal respondeu:

- `GET /api/painelprincipal/retornar-dados-por-empresa` -> `Favor Selecionar a Empresa`
- `GET /api/difal/obter-valores-difal?recalcular=false` -> `Informe o periodo fiscal.`
- `GET /api/nota-fiscal/lista-nota-fiscal-saida-paginacao` -> `Favor Selecionar a Empresa`

### O que funcionou

Funcionou o replay manual stateful com `WebRequestSession`, mantendo a mesma sessao HTTP para:

1. login
2. listagem de empresas
3. apuracao
4. injecao dos cookies de contexto no `cookie jar`
5. `valor-auditoria`
6. `painelprincipal`
7. DIFAL
8. documentos de entrada
9. documentos de saida
10. tarefas

Tambem funcionou o sync real do Lumen via `POST /api/v1/integrations/sittax/sync`, com:

- `dry_run = true` -> sucesso
- `dry_run = false` -> sucesso
- `context_mismatches = 0`
- `failures = 0`

## Sequencia observada e validada

| Ordem | Metodo | Host | Path | Funcao | Resultado confirmado em 2026-07-20 |
| --- | --- | --- | --- | --- | --- |
| 1 | POST | `autenticacao.sittax.com.br` | `/api/auth/login` | autenticar e emitir JWT | sucesso |
| 2 | GET | `api.sittax.com.br` | `/api/empresa/listar-todas-escritorio-empresas-selecao` | listar empresas do escritorio | sucesso |
| 3 | GET | `apuracao.sittax.com.br` | `/api/apuracao/retornar-apuracao-sittax` | consultar apuracao por empresa e competencia | sucesso |
| 4 | POST | `api.sittax.com.br` | `/api/v2/painel-contador/valor-auditoria` | materializar periodo no host API | sucesso |
| 5 | GET | `api.sittax.com.br` | `/api/painelprincipal/retornar-dados-por-empresa` | validar empresa ativa no host API | sucesso com sessao stateful |
| 6 | GET | `api.sittax.com.br` | `/api/difal/obter-valores-difal` | consultar DIFAL | sucesso com sessao stateful |
| 7 | GET | `api.sittax.com.br` | `/api/nota-fiscal/lista-nota-fiscal-entrada-paginacao` | documentos de entrada | sucesso com sessao stateful |
| 8 | GET | `api.sittax.com.br` | `/api/nota-fiscal/lista-nota-fiscal-saida-paginacao` | documentos de saida | sucesso com sessao stateful |
| 9 | GET | `api.sittax.com.br` | `/api/tarefa/paginacao` | tarefas | sucesso |

## Componentes minimos da sessao funcional

Os itens abaixo foram observados como suficientes no replay stateful validado em 2026-07-20:

- header `Authorization: Bearer <jwt>`
- header `Referer: https://app.sittax.com.br/`
- header `Accept: application/json, text/plain, */*`
- cookie `sittax-api-affinity`
- cookie `CnpjDaEmpresaSelecionada`
- cookie `DataInicialSelecionada`
- cookie `IdEscritorioSelecionado`
- cookie `IdGrupoDeEmpresaSelecionado`

## Cookies relevantes observados

### Cookies de contexto

- `CnpjDaEmpresaSelecionada`
  - dominio observado: `.sittax.com.br`
  - funcao: empresa ativa do contexto

- `DataInicialSelecionada`
  - dominio observado: `.sittax.com.br`
  - funcao: periodo fiscal ativo
  - valor observado no replay funcional: `2026-05-01T00:00:00`

- `IdEscritorioSelecionado`
  - dominio observado: `.sittax.com.br`
  - funcao: escritorio ativo da sessao

- `IdGrupoDeEmpresaSelecionado`
  - dominio observado: `.sittax.com.br`
  - funcao: placeholder contextual observado; no replay validado permaneceu vazio

### Cookie de afinidade

- `sittax-api-affinity`
  - dominio observado: `api.sittax.com.br`
  - funcao provavel: afinidade de backend ou balanceamento
  - observacao: o replay stateful funcional preservou esse cookie automaticamente

## Diferenca entre replay stateless e stateful

### Replay stateless

- cada chamada independente
- header `Cookie` montado manualmente
- sem `cookie jar` automatico
- sem preservacao de afinidade do host `api`

Resultado observado:

- `valor-auditoria` podia responder `ok = true`
- `painelprincipal`, DIFAL e documentos continuavam sem contexto valido

### Replay stateful

- uma unica sessao HTTP persistente
- `cookie jar` automatico
- preservacao do cookie de afinidade
- preservacao dos cookies de contexto entre hosts e chamadas

Resultado observado:

- `painelprincipal` respondeu `sucesso = true`
- DIFAL respondeu `sucesso = true`
- documentos de entrada responderam `sucesso = true`
- documentos de saida responderam `sucesso = true`

## Contrato sanitizado por request

- `POST /api/auth/login`
  - body keys observadas: `usuario`, `senha`
  - response keys observadas: `codigo`, `primeiroAcesso`, `token`, `usuario`
  - efeito contextual: emite o JWT usado nos tres hosts

- `GET /api/empresa/listar-todas-escritorio-empresas-selecao`
  - query keys observadas: `idEscritorio`
  - response keys observadas: `$id`, `sucesso`, `empresas`
  - efeito contextual: nao define empresa ativa, mas confirma o escritorio e inicia o uso do host `api`

- `GET /api/apuracao/retornar-apuracao-sittax`
  - query keys observadas: `empresaCnpj`, `periodo`
  - response keys observadas: `ok`, `status`, `erros`, `data`
  - efeito contextual: define o contexto do host `apuracao`

- `POST /api/v2/painel-contador/valor-auditoria`
  - body keys observadas: `periodo`
  - response keys observadas: `ok`, `status`, `erros`, `data`
  - efeito contextual: materializa periodo no host `api`, desde que a sessao correta ja esteja em uso

- `GET /api/painelprincipal/retornar-dados-por-empresa`
  - response keys em sucesso: `$id`, `sucesso`, `nome`, `alertas`, `email`
  - response keys em falha observada: `$id`, `mensagem`, `sucesso`, `status`, `stack`, `details`
  - efeito contextual: confirma empresa ativa do host `api`

- `GET /api/difal/obter-valores-difal`
  - query keys observadas: `recalcular`
  - response keys em sucesso: `$id`, `sucesso`, `mensagem`, `difal`, `possuiMensagemDeAlerta`
  - efeito contextual: depende da empresa e periodo ja ativos no host `api`

- `GET /api/nota-fiscal/lista-nota-fiscal-entrada-paginacao`
  - query keys observadas: `pagina`, `pageSize`, `filtros`, `ordenacao`, `total`
  - response keys observadas: `$id`, `sucesso`, `total`, `totalFiltrado`, `lista`

- `GET /api/nota-fiscal/lista-nota-fiscal-saida-paginacao`
  - query keys observadas: `pagina`, `pageSize`, `filtros`, `ordenacao`, `total`
  - response keys observadas: `$id`, `sucesso`, `total`, `totalFiltrado`, `lista`

- `GET /api/tarefa/paginacao`
  - response keys observadas: `$id`, `sucesso`, `total`, `totalFiltrado`, `lista`
  - observacao: funcionou tanto no portal quanto no replay manual; nao dependeu do mesmo nivel de contexto de empresa

## Implicacoes obrigatorias para o Lumen

- O conector Sittax deve permanecer stateful.
- O conector Sittax nao deve ser reescrito como cliente stateless por request.
- O `httpx.Client` deve preservar cookies entre chamadas.
- O `httpx.Client` deve preservar o cookie `sittax-api-affinity`.
- O contexto de apuracao e o contexto do host `api` continuam separados conceitualmente.
- A sessao deve continuar exclusiva por empresa e competencia.
- O processamento continua obrigatoriamente serial por sessao.
- Nao e permitido alternar empresa dentro da mesma sessao e continuar usando contexto antigo.
- A validacao do host `api` por `painelprincipal` continua necessaria antes de DIFAL e documentos.

## O que nao foi comprovado

- Nao foi observado endpoint explicito de "selecionar empresa" no host `api`.
- Nao foi comprovado que apenas os cookies acima bastam em qualquer nova sessao criada fora do fluxo validado.
- Nao foi provado que chamadas fora da ordem observada sejam equivalentes.
- Nao foi provado que paralelizar empresas na mesma sessao seja seguro.

## Erros que nao devem se repetir

- presumir que apuracao sozinha habilita DIFAL e documentos
- presumir que `Bearer` isolado transforma o host `api` em API stateless
- copiar cookies manualmente entre chamadas avulsas e assumir equivalencia a uma sessao real
- ignorar `sittax-api-affinity`
- continuar chamando DIFAL ou documentos depois de falha de contexto do host `api`
- logar JWT, cookies ou valores sensiveis em texto puro

## Ruido ignorado

- analytics
- OpenReplay
- `cdn-cgi/rum`
- `Notificar/negotiate`
- assets, imagens e fontes
