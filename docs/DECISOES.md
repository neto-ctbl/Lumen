# Decisoes Tecnicas do Lumen

Data de referencia: 2026-07-20

## S7.0 - Sittax observado

- Sittax sera tratado como integracao baseada em endpoints observados do portal web, nao como API publica oficial documentada.
- A integracao Sittax permanecera estritamente read-only.
- A chamada `GET /api/apuracao/retornar-apuracao-sittax?empresaCnpj=...&periodo=...` e o setter oficial do contexto ativo da sessao.
- O contexto ativo da sessao persiste por `empresaCnpj` e `periodo` ate nova chamada de apuracao substituir um ou ambos.
- Endpoints contextuais como DIFAL, painel da empresa e notas fiscais devem ser consultados somente depois da apuracao definir o contexto.
- A primeira versao do conector Sittax deve executar em modo serial por sessao, com sessao exclusiva por empresa/competencia.
- Nao e permitido compartilhar a mesma sessao simultaneamente entre empresas ou competencias diferentes.
- `recalcular=true` e proibido.
- Endpoints de transmissao, fechamento, upload, inclusao, exclusao ou qualquer mutacao externa ficam fora de escopo.
- O health futuro do Sittax deve usar apenas estado local, sem login externo por request do frontend.
- Fixtures de teste do Sittax devem ser integralmente anonimizadas e sinteticas.
- O log bruto `sittax-network-log.jsonl` e somente fonte temporaria de analise e deve permanecer fora do Git.
- O endpoint `POST /api/v2/painel-contador/transmissao` foi classificado como ambiguo e adiado.
- O micro-stage S7.0 e documental e de seguranca; ele nao cria cliente HTTP real, login real, models, migrations ou sync.

## S7.1 - Fundacao tecnica do cliente Sittax

- O cliente Sittax do S7.1 permanece estritamente read-only e limitado a login e listagem de empresas.
- A sessao Sittax nasce stateful e exclusiva, com um unico `httpx.Client` por instancia.
- O JWT do Sittax existe somente em memoria na sessao ativa.
- A senha do Sittax so e usada para montar o body de login no momento da chamada.
- O cliente Sittax nao usa `httpx.Client` global, singleton global ou token global.
- A sessao local usa exclusao mutua por instancia via `session.exclusive()`.
- A mesma sessao nao pode ser usada simultaneamente por threads diferentes.
- `active_company_cnpj` e `active_period` existem apenas como placeholders nulos para compatibilidade com o contexto futuro.
- O S7.1 nao define contexto por apuracao e nao simula contexto ativo.
- O escritorio ativo deve ser resolvido deterministicamente a partir do payload observado de login.
- O fixture mode do Sittax reutiliza os mesmos mappers do cliente real e nao acessa rede.
- O script `check_sittax_connection` valida apenas login e listagem de empresas, sem persistencia e sem PII.
- A homologacao real do S7.1 confirmou o fluxo `login -> escritorio -> empresas` em 2026-07-16.
- O login real do portal Sittax foi aceito com `codigo = 200`; o cliente deve considerar `0` e `200` como sucessos observados de autenticacao.

## S7.2 - Snapshot de empresas Sittax

- O S7.2 persiste apenas snapshot local read-only da listagem de empresas Sittax.
- A identidade da fonte no snapshot e `organization_id + sittax_company_id`.
- A reconciliacao local usa `organization_id + cnpj` contra `external_companies`.
- O snapshot usa `company_id` nullable para referenciar `external_companies.id` somente quando houver match univoco.
- `MATCHED`, `UNMATCHED`, `AMBIGUOUS` e `INVALID_CNPJ` devem ser tratados explicitamente.
- `state_registration` continua nullable no banco; `ISENTO` segue apenas como representacao de interface futura.
- Ausencia na listagem Sittax nao implica exclusao nem inativacao automatica de empresa local.
- `dry_run` autentica e reconcilia em memoria sem persistir snapshots, runs ou auditoria.
- `integration_sync_runs` do S7.2 guardam apenas contadores, erros sanitizados e metadata segura.
- O sync Sittax permanece restrito a `POST /api/auth/login` e `GET /api/empresa/listar-todas-escritorio-empresas-selecao`.

## S7.3 - Apuracao Sittax por empresa e competencia

- A apuracao do Sittax passa a ser consumida somente por `GET /api/apuracao/retornar-apuracao-sittax`.
- O contexto ativo da sessao deve ser limpo antes de cada tentativa de apuracao.
- O contexto ativo da sessao so pode ser confirmado apos resposta HTTP valida, JSON valido, envelope de negocio valido, CNPJ coerente e competencia coerente.
- Qualquer falha na apuracao limpa o contexto ativo e bloqueia persistencia.
- A CLI operacional recebe somente `YYYY-MM` e converte para `MM/YYYY` apenas na chamada externa.
- A competencia precisa existir previamente em `fiscal_periods`.
- O snapshot de apuracao usa idempotencia por `organization_id + sittax_company_snapshot_id + fiscal_period_id`.
- O sync de apuracoes permanece serial, read-only e sem chamar DIFAL, documentos fiscais, painel, tarefas ou qualquer mutacao externa.

## S7.4 - Handoff de contexto entre hosts

- O contexto de `apuracao.sittax.com.br` e o contexto de `api.sittax.com.br` sao tratados separadamente na sessao local.
- Sucesso da apuracao nao autoriza mais, por si so, chamadas de DIFAL e documentos.
- O host `api.sittax.com.br` deve ser confirmado antes de DIFAL e documentos por uma chamada observada em rede e validada por envelope.
- `POST /api/v2/painel-contador/valor-auditoria` foi aceito como bootstrap observado de periodo no host API.
- `GET /api/painelprincipal/retornar-dados-por-empresa` foi aceito como validacao do contexto do host API, nao como sucesso silencioso presumido.
- Falha no handoff do host API limpa apenas o contexto da API e interrompe a cadeia contextual da empresa.
- Nao e permitido chamar DIFAL ou documentos depois de um `SittaxContextMismatchError` do host API.
- O replay stateless com `Bearer` isolado ou com header `Cookie` montado manualmente nao e considerado equivalente ao comportamento do portal.
- O replay stateful validado em 2026-07-20 confirmou que o host `api.sittax.com.br` depende de sessao web persistente com `cookie jar`.
- O conector oficial do Lumen deve permanecer stateful por sessao e preservar cookies entre chamadas.
- O cookie `sittax-api-affinity` passa a ser tratado como parte relevante da sessao observada.
- Os cookies `CnpjDaEmpresaSelecionada`, `DataInicialSelecionada`, `IdEscritorioSelecionado` e `IdGrupoDeEmpresaSelecionado` passam a ser tratados como contexto observado relevante do host `api`.
- O handoff stateful `login -> empresas -> apuracao -> valor-auditoria -> painelprincipal -> DIFAL/documentos` foi validado na pratica em 2026-07-20.
- Ainda nao foi comprovado endpoint explicito de "selecionar empresa" no host `api`; a implementacao deve continuar usando apenas a sequencia observada e a sessao stateful validada.

## S8.0 - Contrato observado da Econet

- A Econet sera tratada como fonte indicativa de CNAE, tributacao e obrigacoes, nao como fonte oficial de regime e entregas.
- O Acessorias permanece como fonte oficial de regime e entregas.
- O login da Econet continuara manual.
- CAPTCHA nao sera automatizado nem contornado.
- Artefatos brutos da Econet nao serao versionados.
- Fixtures da Econet devem ser sinteticas ou rigorosamente sanitizadas.
- O cache futuro da Econet sera orientado por CNAE.
- A consulta futura da Econet nao deve ocorrer a cada abertura de tela.
- O S8.0 nao cria decisao fiscal automatica.
