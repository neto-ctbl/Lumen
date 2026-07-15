# Sittax Observed Contract for Lumen S7.1

Data de referencia: 2026-07-15

## Natureza do contrato

- Os endpoints abaixo foram observados no portal web do Sittax durante navegacao autorizada.
- Este material nao representa uma API publica oficial documentada.
- O portal e os payloads podem mudar sem aviso.
- O contrato depende de autorizacao legitima de uso.
- O Lumen utilizara apenas leitura.
- Nao havera transmissao, recalculo ou qualquer mutacao externa.
- O contrato deve ser revalidado quando o portal mudar.

## Estado atual de implementacao

- S7.0 concluiu apenas documentacao, fixtures anonimizadas e schemas observados.
- S7.1 implementa somente autenticacao read-only, sessao exclusiva local e listagem de empresas.
- S7.1 nao implementa apuracao, DIFAL, documentos fiscais, painel da empresa, tarefas, sync, snapshots, endpoint manual ou health funcional.

## Classificacoes usadas

- `CORE_READ_ONLY`
- `CONTEXT_SETTER`
- `CONTEXT_DEPENDENT`
- `SUPPORTING_READ_ONLY`
- `AMBIGUOUS_DEFERRED`
- `TELEMETRY_IGNORE`
- `OUT_OF_SCOPE`

## Contexto persistente por empresa e competencia

A consulta de apuracao define o contexto ativo por `empresaCnpj` e `periodo`.
Todos os endpoints contextuais seguintes utilizam esse ultimo contexto ate
que uma nova consulta de apuracao o substitua.

Consequencias obrigatorias para a arquitetura do conector:

- uma sessao deve ser exclusiva por empresa/competencia durante o processamento;
- a primeira implementacao deve ser serial por sessao;
- nao e permitido alternar Empresa A, depois Empresa B, e voltar a consultar dados contextuais de Empresa A na mesma sessao;
- paralelismo futuro so sera aceitavel com sessoes totalmente isoladas.

## Endpoints observados

### Login

- Host: `autenticacao.sittax.com.br`
- Metodo: `POST`
- Path: `/api/auth/login`
- Autenticacao: nao aplicavel; este endpoint gera o JWT
- Parametros: body observado fora do Git; nao deve ser logado nem versionado
- Envelope observado: objeto com `codigo`, `primeiroAcesso`, `token`, `usuario`
- Campos relevantes: `token`, `usuario.id`, `usuario.email`, `usuario.nome`, `usuario.escritorio`, `usuario.role`
- Paginacao: nao
- Classificacao: `CORE_READ_ONLY`
- Dependencia de contexto: nao
- Riscos: vazamento de senha, JWT, cookies e contexto de escritorio
- Uso previsto no Lumen: autenticacao futura e descoberta do escritorio/usuario
- Implementacao atual do S7.1: login read-only com body observado `usuario` + `senha`, token somente em memoria e sem persistencia

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
- Implementacao atual do S7.1: listagem read-only por `idEscritorio` resolvido no login, com mapper sem persistencia

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
- Dependencia de contexto: define o contexto ativo
- Riscos: consulta altera o contexto ativo da sessao e pode invalidar leituras contextuais anteriores
- Uso previsto no Lumen: snapshot principal de apuracao e definicao de contexto da sessao

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
- Dependencia de contexto: usa a ultima empresa/competencia definida pela apuracao
- Riscos: nao chamar antes da apuracao; `recalcular=true` e proibido
- Uso previsto no Lumen: snapshot de DIFAL read-only

### Documentos fiscais de entrada

- Host: `api.sittax.com.br`
- Metodo: `GET`
- Path: `/api/nota-fiscal/lista-nota-fiscal-entrada-paginacao`
- Parametros observados: `filtros`, `ordenacao`, `pageSize`, `pagina`, `total`
- Envelope observado: objeto com `$id`, `sucesso`, `total`, `totalFiltrado`, `lista`
- Campos relevantes por item: `id`, `chave_acesso`, `numero`, `modelo`, `data_emissao`, `data_entrada`, `data_competencia`, `emitente_nome`, `emitente_uf`, `cfops`, `valor_total`, `tem_xml`, `status`, `tipo_importacao`, `importada`
- Paginacao: sim
- Autenticacao: JWT Bearer observado no portal
- Classificacao: `CONTEXT_DEPENDENT`
- Dependencia de contexto: usa a ultima empresa/competencia definida pela apuracao
- Riscos: primeira pagina nao representa o conjunto completo; filtros observados podem mudar
- Uso previsto no Lumen: snapshot paginado de notas de entrada

### Documentos fiscais de saida

- Host: `api.sittax.com.br`
- Metodo: `GET`
- Path: `/api/nota-fiscal/lista-nota-fiscal-saida-paginacao`
- Parametros observados: `filtros`, `ordenacao`, `pageSize`, `pagina`, `total`
- Envelope observado: objeto com `$id`, `sucesso`, `total`, `totalFiltrado`, `lista`
- Campos relevantes por item: `id`, `chave_acesso`, `numero`, `modelo`, `data_emissao`, `data_competencia`, `destinatario_nome`, `destinatario_uf`, `emitente_cpf_cnpj`, `valor_total`, `valor_base_calculo`, `valor_deducoes`, `desconto_condicionado`, `desconto_incondicionado`, `tem_xml`, `status`
- Paginacao: sim
- Autenticacao: JWT Bearer observado no portal
- Classificacao: `CONTEXT_DEPENDENT`
- Dependencia de contexto: usa a ultima empresa/competencia definida pela apuracao
- Riscos: primeira pagina nao representa o conjunto completo
- Uso previsto no Lumen: snapshot paginado de notas de saida

### Painel da empresa

- Host: `api.sittax.com.br`
- Metodo: `GET`
- Path: `/api/painelprincipal/retornar-dados-por-empresa`
- Parametros observados: nenhum na chamada observada
- Envelope observado: objeto com `$id`, `sucesso`, `nome`, `email`, `alertas`
- Campos relevantes por alerta: `id`, `tipoDoAlerta`, `tipoStatusAlerta`, `mensagem`, `ciente`, `historicoDoAlerta`
- Paginacao: nao
- Autenticacao: JWT Bearer observado no portal
- Classificacao: `CONTEXT_DEPENDENT`
- Dependencia de contexto: usa a ultima empresa/competencia definida pela apuracao
- Riscos: sem contexto valido pode refletir empresa/competencia erradas
- Uso previsto no Lumen: enriquecimento de alertas e dados auxiliares da empresa

### Tarefas

- Host: `api.sittax.com.br`
- Metodo: `GET`
- Path: `/api/tarefa/paginacao`
- Parametros observados: nao conclusivos no log capturado
- Envelope observado: objeto com `$id`, `sucesso`, `total`, `totalFiltrado`, `lista`
- Campos relevantes por item: `id`, `guid`, `titulo`, `descricaoString`, `nomeEmpresa`, `periodo`, `status`, `usuarioId`, `usuarioNome`, `dataCriacao`, `dataFimProcessamento`, `tempoProcessamento`, `possuiArquivo`, `nomeArquivo`, `extensaoArquivo`
- Paginacao: sim
- Autenticacao: JWT Bearer observado no portal
- Classificacao: `SUPPORTING_READ_ONLY`
- Dependencia de contexto: nao comprovada no log capturado
- Riscos: comportamento contextual nao deve ser presumido sem nova observacao
- Uso previsto no Lumen: snapshot read-only de fila operacional e transmissao/tarefa observada

### Endpoints auxiliares de leitura

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
  - `POST /api/v2/painel-contador/valor-auditoria`
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
