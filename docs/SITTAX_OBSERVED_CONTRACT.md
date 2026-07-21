# Sittax Observed Contract for Lumen S7.4

Data de referencia: 2026-07-20

## Natureza do contrato

- Os endpoints abaixo foram observados no portal web do Sittax durante navegacao autorizada.
- Este material nao representa API publica oficial documentada.
- O portal, os cookies e os envelopes podem mudar sem aviso.
- O contrato depende de autorizacao legitima de uso.
- O Lumen utiliza apenas leitura.
- Nao havera transmissao, recalculo ou qualquer mutacao externa.
- O contrato deve ser revalidado quando o portal mudar ou quando o replay stateful deixar de reproduzir o comportamento do portal.

## Estado atual de implementacao

- S7.0 concluiu documentacao inicial, fixtures anonimizadas e schemas observados.
- S7.1 implementou autenticacao read-only, sessao exclusiva local e listagem de empresas.
- S7.2 implementou snapshot local read-only da listagem de empresas.
- S7.3 implementou snapshot local read-only da apuracao por empresa e competencia.
- S7.4 implementou DIFAL, documentos, tarefas, runs operacionais e handoff stateful do host `api`.
- Validacao real controlada executada em 2026-07-16 confirmou login, resolucao de escritorio e listagem de `157` empresas em tenant autorizado.
- Validacao real do sync operacional executada em 2026-07-20 confirmou `dry_run = SUCCESS` e `write run = SUCCESS` no endpoint local `POST /api/v1/integrations/sittax/sync`.
- Replay manual stateful executado em 2026-07-20 confirmou `painelprincipal`, DIFAL, documentos de entrada, documentos de saida e tarefas na mesma sessao HTTP.

## Classificacoes usadas

- `CORE_READ_ONLY`
- `CONTEXT_SETTER`
- `CONTEXT_DEPENDENT`
- `SUPPORTING_READ_ONLY`
- `AMBIGUOUS_DEFERRED`
- `TELEMETRY_IGNORE`
- `OUT_OF_SCOPE`

## Modelo real de sessao

### Regra principal

O Sittax, para o host `api.sittax.com.br`, comporta-se como sessao web stateful e nao como API stateless pura.

### Componentes da sessao observada

- JWT Bearer retornado pelo login
- cookie de afinidade do host `api`
- cookies de contexto em `.sittax.com.br`
- ordem correta das chamadas
- reutilizacao do mesmo cliente HTTP

### Cookies relevantes observados em 2026-07-20

- `sittax-api-affinity`
- `CnpjDaEmpresaSelecionada`
- `DataInicialSelecionada`
- `IdEscritorioSelecionado`
- `IdGrupoDeEmpresaSelecionado`

### Consequencias obrigatorias para o conector

- uma sessao deve ser exclusiva por empresa e competencia durante o processamento
- a implementacao deve permanecer serial por sessao
- nao e permitido alternar Empresa A, depois Empresa B, e voltar a consultar dados contextuais de Empresa A na mesma sessao
- paralelismo futuro so sera aceitavel com sessoes totalmente isoladas
- falha no handoff do host `api` deve interromper a cadeia contextual da empresa antes de DIFAL e documentos
- o cliente deve preservar o `cookie jar` e nao reconstruir chamadas contextuais como requests isolados

## Endpoints observados

### Login

- Host: `autenticacao.sittax.com.br`
- Metodo: `POST`
- Path: `/api/auth/login`
- Autenticacao: nao aplicavel; este endpoint gera o JWT
- Parametros observados: body com `usuario`, `senha`
- Envelope observado: objeto com `codigo`, `primeiroAcesso`, `token`, `usuario`
- Campos relevantes: `token`, `usuario.id`, `usuario.email`, `usuario.nome`, `usuario.escritorio`, `usuario.role`
- Paginacao: nao
- Classificacao: `CORE_READ_ONLY`
- Dependencia de contexto: nao
- Riscos: vazamento de senha, JWT, cookies e contexto de escritorio
- Uso previsto no Lumen: autenticacao e descoberta do escritorio/usuario
- Validacao real: sucesso em 2026-07-20 no replay manual stateful e no cliente do Lumen

### Empresas do escritorio

- Host: `api.sittax.com.br`
- Metodo: `GET`
- Path: `/api/empresa/listar-todas-escritorio-empresas-selecao`
- Parametros observados: `idEscritorio`
- Envelope observado: objeto com `$id`, `sucesso`, `empresas`
- Campos relevantes: `id`, `cnpj`, `nome`, `fantasia`, `uf`, `inscricaoEstadual`, `homologada`, `usaRegimeDeCaixa`
- Paginacao: nao observada
- Autenticacao: JWT Bearer observado no portal
- Classificacao: `CORE_READ_ONLY`
- Dependencia de contexto: nao
- Riscos: depende do escritorio selecionado; IDs internos nao devem ser tratados como estaveis
- Uso previsto no Lumen: conciliacao com `external_companies` e cache de empresa Sittax
- Validacao real: sucesso em 2026-07-20

### Apuracao

- Host: `apuracao.sittax.com.br`
- Metodo: `GET`
- Path: `/api/apuracao/retornar-apuracao-sittax`
- Parametros observados: `empresaCnpj`, `periodo`
- Envelope observado: objeto com `ok`, `status`, `erros`, `data`
- Campos relevantes observados em `data`: `id`, `periodoFiscal`, `escritorioNome`, `valorDas`, `numeroDas`, `numeroDeclaracao`, `numeroExtrato`, `rba`, `rbt12`, `receitaLiquida`, `receitaProdutos`, `receitaServicos`, `folhaDePagamentos`, `percentualFatorR`, `tipoDaTransmissao`, `mensagens`, `inconsistencias`, `resumosTributacaoSittax`, `resumosTributacaoXml`, `dataHoraTransmissao`
- Paginacao: nao
- Autenticacao: JWT Bearer observado no portal
- Classificacao: `CORE_READ_ONLY`, `CONTEXT_SETTER`
- Dependencia de contexto: define o contexto do host `apuracao`
- Riscos: consulta altera o contexto ativo da sessao e pode invalidar leituras contextuais anteriores
- Uso previsto no Lumen: snapshot principal de apuracao e definicao do contexto da sessao
- Validacao real: sucesso em 2026-07-20

### Bootstrap de periodo do host API

- Host: `api.sittax.com.br`
- Metodo: `POST`
- Path: `/api/v2/painel-contador/valor-auditoria`
- Parametros observados: body com `periodo`
- Envelope observado: objeto com `ok`, `status`, `erros`, `data`
- Paginacao: nao
- Autenticacao: JWT Bearer observado no portal
- Classificacao: `SUPPORTING_READ_ONLY`
- Dependencia de contexto: depende da sessao certa; sozinho nao garante empresa ativa
- Riscos: replay stateless pode devolver `ok = true` sem materializar o contexto completo
- Uso previsto no Lumen: parte obrigatoria do handoff para o host `api`
- Validacao real: sucesso em 2026-07-20 tanto no cliente do Lumen quanto no replay stateful

### Painel da empresa

- Host: `api.sittax.com.br`
- Metodo: `GET`
- Path: `/api/painelprincipal/retornar-dados-por-empresa`
- Parametros observados: nenhum na chamada observada
- Envelope observado em sucesso: objeto com `$id`, `sucesso`, `nome`, `email`, `alertas`
- Envelope observado em falha: objeto com `$id`, `mensagem`, `sucesso`, `status`, `stack`, `details`
- Campos relevantes por alerta: `id`, `tipoDoAlerta`, `tipoStatusAlerta`, `mensagem`, `ciente`, `historicoDoAlerta`
- Paginacao: nao
- Autenticacao: JWT Bearer observado no portal
- Classificacao: `CONTEXT_DEPENDENT`
- Dependencia de contexto: depende de empresa ativa e periodo ativo materializados no host `api`
- Riscos: em replay stateless falhou com `Favor Selecionar a Empresa`; so funcionou com sessao persistente
- Uso previsto no Lumen: validacao forte do contexto do host `api` antes de DIFAL e documentos; enriquecimento com alertas
- Validacao real: sucesso em 2026-07-20 com `WebRequestSession`

### DIFAL

- Host: `api.sittax.com.br`
- Metodo: `GET`
- Path: `/api/difal/obter-valores-difal`
- Parametros observados: `recalcular`
- Envelope observado: objeto com `$id`, `sucesso`, `mensagem`, `possuiMensagemDeAlerta`, `difal`
- Campos relevantes observados em `difal`: `id`, `possuiGuia`, `numeroDareGuiaRevenda`, `numeroDareGuiaUsoConsumoImobilizado`, `valorGuiaRevenda`, `valorGuiaRevendaUtilizandoCredito`, `valorGuiaUsoConsumoImobilizadoUtilizandoCredito`, `totalTodasCompras`, `totalReceitaRevendaInterestadual`, `totalReceitaUsoConsumoImobilizado`, `dataFechamento`, `dataTransmissao`, `creditos`, `temNotasComReferenciaSemTipo`
- Paginacao: nao
- Autenticacao: JWT Bearer observado no portal
- Classificacao: `CONTEXT_DEPENDENT`
- Dependencia de contexto: exige sessao stateful com contexto ativo confirmado no host `api`
- Riscos: `recalcular=true` continua proibido; replay stateless devolveu `Informe o periodo fiscal.`
- Uso previsto no Lumen: snapshot de DIFAL read-only
- Validacao real: sucesso em 2026-07-20 com `sucesso = true`

### Documentos fiscais de entrada

- Host: `api.sittax.com.br`
- Metodo: `GET`
- Path: `/api/nota-fiscal/lista-nota-fiscal-entrada-paginacao`
- Parametros observados: `filtros`, `ordenacao`, `pageSize`, `pagina`, `total`
- Envelope observado: objeto com `$id`, `sucesso`, `total`, `totalFiltrado`, `lista`
- Campos relevantes por item: `id`, `chave_acesso`, `numero`, `modelo`, `status`, `data_emissao`, `data_entrada`, `data_competencia`, `emitente_nome`, `emitente_uf`, `cfops`, `valor_total`, `tem_xml`, `tipo_importacao`, `importada`
- Paginacao: sim
- Autenticacao: JWT Bearer observado no portal
- Classificacao: `CONTEXT_DEPENDENT`
- Dependencia de contexto: exige sessao stateful com contexto ativo confirmado no host `api`
- Riscos: primeira pagina nao representa o conjunto completo; filtros observados podem mudar
- Uso previsto no Lumen: snapshot paginado de notas de entrada
- Validacao real: sucesso em 2026-07-20 com `sucesso = true`, `total = 273`, `totalFiltrado = 31`

### Documentos fiscais de saida

- Host: `api.sittax.com.br`
- Metodo: `GET`
- Path: `/api/nota-fiscal/lista-nota-fiscal-saida-paginacao`
- Parametros observados: `filtros`, `ordenacao`, `pageSize`, `pagina`, `total`
- Envelope observado: objeto com `$id`, `sucesso`, `total`, `totalFiltrado`, `lista`
- Campos relevantes por item: `id`, `numero`, `modelo`, `status`, `data_emissao`, `data_competencia`, `destinatario_nome`, `destinatario_uf`, `emitente_cpf_cnpj`, `valor_total`, `valor_base_calculo`, `valor_deducoes`, `desconto_condicionado`, `desconto_incondicionado`, `tem_xml`
- Paginacao: sim
- Autenticacao: JWT Bearer observado no portal
- Classificacao: `CONTEXT_DEPENDENT`
- Dependencia de contexto: exige sessao stateful com contexto ativo confirmado no host `api`
- Riscos: primeira pagina nao representa o conjunto completo
- Uso previsto no Lumen: snapshot paginado de notas de saida
- Validacao real: sucesso em 2026-07-20 com `sucesso = true`, `total = 137`, `totalFiltrado = 8`

### Tarefas

- Host: `api.sittax.com.br`
- Metodo: `GET`
- Path: `/api/tarefa/paginacao`
- Parametros observados: nao conclusivos no primeiro log; chamadas reais sem query tambem responderam
- Envelope observado: objeto com `$id`, `sucesso`, `total`, `totalFiltrado`, `lista`
- Campos relevantes por item: `id`, `guid`, `titulo`, `descricaoString`, `nomeEmpresa`, `periodo`, `status`, `usuarioId`, `usuarioNome`, `dataCriacao`, `dataFimProcessamento`, `tempoProcessamento`, `possuiArquivo`, `nomeArquivo`, `extensaoArquivo`
- Paginacao: sim
- Autenticacao: JWT Bearer observado no portal
- Classificacao: `SUPPORTING_READ_ONLY`
- Dependencia de contexto: nao exigiu o mesmo contexto forte de empresa
- Riscos: datas reais vieram com fracao de segundos heterogenea, incluindo `2026-07-20T20:20:01.53`; o parser local deve continuar aceitando fracao curta e longa
- Uso previsto no Lumen: snapshot read-only de fila operacional e transmissao/tarefa observada
- Validacao real: sucesso em 2026-07-20

## Endpoints auxiliares de leitura

- `GET /api/escritorio/lista-escritorios-para-selecionar`
  - Classificacao: `SUPPORTING_READ_ONLY`
  - Risco: payload observado inclui `apiKeyAcessorias`; esse campo jamais deve aparecer em fixture ou log interno
- `GET /api/escritorio/listar-escritorios-do-grupo-escritorios`
  - Classificacao: `SUPPORTING_READ_ONLY`
- `GET /api/tipo-da-nota/retornar-tipo-das-notas`
  - Classificacao: `SUPPORTING_READ_ONLY`
- `GET /api/acessos/retornar-todas-claims`
  - Classificacao: `SUPPORTING_READ_ONLY`

## Endpoints ambiguos e adiados

- `POST /api/v2/painel-contador/transmissao`
  - Classificacao: `AMBIGUOUS_DEFERRED`
  - Motivo: nome e metodo indicam acao potencialmente sensivel
  - Regra: nao chamar, nao incluir no cliente inicial, nao tratar como seguro

- Outros endpoints `painel-contador`
  - `POST /api/v2/painel-contador/apuracao`
  - `POST /api/v2/painel-contador/auditoria`
  - `POST /api/v2/painel-contador/lista-apuracao-transmitido`
  - Classificacao inicial: `AMBIGUOUS_DEFERRED`

## Telemetria ignorada

- `POST app.sittax.com.br/cdn-cgi/rum`
- `POST openreplay.sittax.com.br/ingest/v1/web/start`
- `POST /Notificar/negotiate`
- publicidade, trackers e monitoramento do navegador

Classificacao: `TELEMETRY_IGNORE`

## Fora de escopo

- transmissao
- recalculo
- fechamento
- edicao
- exclusao
- inclusao
- upload
- qualquer mutacao externa

Classificacao: `OUT_OF_SCOPE`
