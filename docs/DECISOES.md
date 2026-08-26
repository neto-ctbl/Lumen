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

## S8.1 - Parser offline e cache por CNAE

- O cache do S8.1 foi materializado como global por `cnae` normalizado, nao por organizacao.
- O resultado do S8.1 continua indicativo; ele nao altera regime oficial, nao cria pendencia fiscal e nao gera `fiscal_obligation_statuses`.
- O parser da Econet no S8.1 e puro e offline; ele nao faz request, nao conhece cookie e nao conhece credencial.
- `econet_id_cnae` continua separado do CNAE e nunca deve ser calculado localmente.
- Percentuais tributarios da Econet usam `Decimal`, nunca `float`.
- O parser so faz mapping de obrigacoes quando o alias e explicitamente seguro: `DCTFWeb`, `EFD-Contribuicoes` e `EFD-Reinf`.
- Obrigacoes desconhecidas nao serao mapeadas por aproximacao; elas permanecem em `unmapped_obligations`.
- Fator R nao deve ser inferido sem texto observado; ausencia de prova permanece `NOT_OBSERVED`.
- Mensagens negativas de Simples ou SIMEI sao resultados validos de negocio, nao erro tecnico do parser.
- O TTL padrao do cache da Econet ficou em `180` dias como constante de dominio local do servico.
- Persistencia com `content_hash` identico continua `UNCHANGED`, mas renova `retrieved_at` e `expires_at`.
- O payload normalizado do S8.1 nao guarda HTML bruto, token, cookie, header ou sessao.

## S8.2 - Sessao manual assistida e health local

- A sessao assistida da Econet fica somente em memoria do processo da API.
- O S8.2 importa apenas cookies allowlisted e descarta analytics.
- O S8.2 nao usa `localStorage`, Redis, banco, `integration_sync_runs` ou arquivo carregado automaticamente no boot.
- O probe da Econet e explicito e administrativo; o health local nao faz chamada externa.
- O cliente HTTP da Econet ficou restrito ao host `www.econeteditora.com.br` e aos endpoints observados de `regimes_cnae`.
- O helper operacional exporta somente cookies permitidos para arquivo temporario ignorado no Git.

## S8.3 - Catalogo CNAE, Fator R potencial e NFS-e canonica

- `company_cnaes` e a representacao relacional canonica dos CNAEs da empresa.
- `0000-0/00` e placeholder invalido e nao pode permanecer ativo no catalogo relacional.
- A Econet nao cria o CNAE da empresa; ela apenas enriquece CNAEs cadastrados.
- Potencial cadastral de Fator R nao equivale a uso efetivo por competencia.
- O CNAE efetivamente usado sera determinado no S10 pela NFS-e normalizada.
- ABRASF usa `CodigoCnae`; o layout nacional usa `cTribMun` com validacao adicional.
- Ausencia de texto de Fator R no HTML nao equivale a `false`.
- HTML bruto da Econet nao e persistido.
- O client da Econet deve decodificar HTML a partir de bytes allowlisted e nunca confiar apenas em `response.text`.
- Mudanca no parser invalida cache anterior por `parser_version`; cache fresco exige versao igual a atual.
- O backend administrativo da Econet aceita ate `50` CNAEs por lote; o uso normal/futuro portal deve ficar em `25`.
- O potencial cadastral de Fator R pode usar inferencia local segura sobre cache fresco quando a combinacao de Simples e anexos ja provar `NOT_APPLICABLE`.

## S8.3.1 - Canonicalizacao do Fator R no cache da Econet

- A regra oficial adotada no parser e no cache passa a ser: `Fator R >= 28% => Anexo III` e `Fator R < 28% => Anexo V`.
- Quando o HTML da Econet expressar caso positivo de Fator R, o armazenamento canonico fica em `simples_annex_default = V` e `simples_annex_conditional = III`, independentemente da ordem textual observada.
- A deteccao de Fator R nao deve usar mencoes incidentais em `Nota ECONET`; ela precisa partir da regra tributaria estruturada do bloco principal do Simples.
- `factor_r_applicable = true` sem combinacao canonica coerente entre anexos passa a ser tratado como sinal de cache historico inconsistente e exige refresh direcionado.

## S6.2 - Backfill operacional do Acessorias

- O regime tributario atual oficial da empresa no Lumen e o `regime_canonical` do `acessorias_company_snapshots` vinculado a empresa local.
- O regime atual oficial nao pertence a `external_companies`.
- O schema atual nao possui historico legal de regimes; o snapshot do Acessorias representa somente o regime atual observado.
- O snapshot atual do Acessorias nao deve ser aplicado retroativamente a competencias antigas sem outra evidencia.
- O backfill do Acessorias foi dividido em duas fases: uma sincronizacao cadastral unica para estado atual e um processamento serial de entregas por competencia.
- O backfill reutiliza apenas tabelas e servicos existentes; nenhuma migration, tabela nova ou coluna nova foi necessaria.
- A retomada operacional do backfill ocorre por idempotencia de snapshots e `fiscal_obligation_statuses`, sem `--resume` heuristico nesta primeira versao.
- O backfill do Acessorias permanece estritamente read-only contra a origem externa e usa somente os endpoints `GET` oficiais de empresas e entregas.
- Labels reais de regime do Acessorias devem ser normalizados para os canonicos internos, incluindo variantes longas de Simples, Lucro Presumido, Lucro Real e `Filial - Simples Nacional`.
- `Filial - Regime Normal` deve herdar o regime canonico da mesma raiz de CNPJ quando houver exatamente um regime mapeado no grupo da matriz/filial.
- `EntGuiaLida` nao deve ser persistido cru quando vier como label longa; o sync deve normalizar para codigos curtos compativeis com o schema atual.
- O filtro `--fiscal-only` existe como opcao operacional e limita o snapshot de entregas a itens `Tipo = O` que sejam obrigacoes mapeadas ou pertencam ao departamento fiscal.
- O comportamento padrao do sync e do backfill continua sem filtro, preservando rastreabilidade maxima quando `--fiscal-only` nao for informado.

## S9.0 - Dominio Folha documental

- Dominio Folha passa a ser integracao documental baseada no PDF `Resumo Mensal`.
- O coletor Windows e opcional e nao participa do nucleo online do Lumen.
- Upload manual do PDF continuara suportado nos stages seguintes.
- O caminho principal do S9 usa PDF com camada textual; OCR fica fora do caminho principal.
- `source_payroll_competence` preserva a competencia da folha e `assessment_competence` representa o mes seguinte.
- A regra `folha M -> apuracao M+1` precisa existir no contrato, nos testes, nas fixtures e no manifest.
- O PDF prova movimento de folha, nao entrega de DCTFWeb.
- Ausencia no PDF nao equivale a folha zerada.
- O matching futuro usara CNPJ.
- A idempotencia futura do arquivo usara SHA-256, nao nome, tamanho ou timestamp.
- O coletor usa `.partial.pdf` e `os.replace` para preservar o ultimo PDF valido ate a nova validacao.

## S9.2 - Persistencia, importador, matching e evidencias

- O S9.2 cria apenas `dominio_payroll_imports` e `dominio_payroll_company_movements`.
- O PDF nao e persistido como blob, base64 ou texto integral na tabela de imports.
- A idempotencia de import ficou em `organization_id + file_sha256`.
- O matching automatico do Dominio usa somente `organization_id + cnpj`.
- `source_payroll_competence` e `assessment_competence` permanecem separadas no banco.
- `fiscal_period_id` do movimento aponta sempre para a competencia de apuracao `M+1`, nunca para a competencia original da folha.
- `rubrics_summary` ficou consolidado em JSONB deterministico; nao existe tabela de rubricas no MVP.
- `fiscal_evidences` do Dominio so nascem para movimentos `MATCHED`.
- `integration_sync_runs` e `audit_log` guardam apenas agregados seguros; `raw_text`, CNPJ e rubricas completas ficam fora desses registros.
- `--dry-run` executa parser e matching, mas nao grava import, movimento, periodo, evidencia, sync run ou auditoria.
- Duplicidade concluida pelo mesmo hash e `no-op`; retry de `FAILED` reutiliza a mesma linha de import.
- O S9.2 nao altera `fiscal_obligation_statuses`, nao marca DCTFWeb como entregue e nao antecipa regras do S9.3.
- O fluxo mensal canonico do Dominio fica definido como um PDF por competencia com filtro `Ativas`.
- `selection_scope` deve ser normalizado deterministicamente; manifests legados `Ativas` passam a ser inferidos como `ACTIVE_COMPANIES`.
- `target_company_count` e `target_list_sha256` pertencem somente ao escopo `FACTOR_R` e nao devem vazar para imports `Ativas`.
- A janela historica de 12 meses para Fator R deve ser montada a partir dos movimentos persistidos; filtro `Fator R` e modo intervalo ficam opcionais para auditoria, diagnostico ou contingencia.
- O relatorio Dominio comprova movimento de folha/eSocial e componente DP, mas nao comprova transmissao da DCTFWeb nem fato gerador da REINF.

## S9.3 - Origem esperada da DCTFWeb

- O S9.3 persiste uma avaliacao derivada e auditavel por `organization_id + external_company_id + fiscal_period_id`, sem atualizar o status da obrigacao.
- O universo do S9.3 e toda empresa atualmente ativa (`ExternalCompany.active = true`) da organizacao; como ainda nao ha historico de ativacao por competencia, essa e uma limitacao operacional documentada.
- Domínio canônica `ACTIVE_COMPANIES` e fonte de cobertura DP; import `FACTOR_R` nao substitui o relatorio mensal.
- DCTFWeb e interpretada operacionalmente como eSocial + EFD-Reinf + MIT: eSocial/Domínio para DP, REINF/MIT para Fiscal.
- REINF e detectada apenas por obrigacao/evidencia canonica `REINF`.
- MIT e detectado apenas a partir da PA `2025-01` pelas obrigacoes canonicas `PIS` e `COFINS`; DAS, regime tributario e `EFD_CONTRIBUICOES` nao inferem MIT.
- Entrega Acessorias mapeada canonicamente para `DCTFWEB`, assim como status ou evidencia canonicos, observa DCTFWeb mas nao decide isoladamente sua origem DP/Fiscal.
- A auditoria de `2026-08-21` confirmou que o snapshot `2026-07` nao possui status/evidencia `PIS` ou `COFINS`, nem fontes canonicas DCTFWeb; `MIT = 0` e `dctfweb_observed = 0` representam ausencia das fontes locais, nao conclusao juridica.
- Empresa ativa sem DP, REINF, MIT ou DCTFWeb observados fica `UNDETERMINED` com `NO_DCTFWEB_COMPONENT_OBSERVED`, departamento esperado nulo e sem alerta acionavel.
- Falta do relatorio mensal Dominio gera no maximo um alerta por organizacao e periodo, com `company_id = null`.
- `expected_origin` e `expected_responsible_department` sao sinais operacionais esperados, nao confirmacao de entrega ou conclusao juridica.

## S9.4.0 - Enriquecimento monetario estruturado do Dominio

- O bloqueio real do `schema_version = 1` era perder os valores monetarios por rubrica ao persistir somente sinais, codigos e totais gerais de bloco.
- `rubrics_summary` evoluiu para `schema_version = 2` sem migration, preservando compatibilidade com `codes`, `signals`, `blocks` e `rubric_count`.
- O resumo monetario do Dominio e apenas materia-prima estruturada; ele nao e `FS12` oficial e nao substitui apuracao fiscal.
- Toda classificacao monetaria do S9.4.0 precisa ser conservadora, baseada em codigo observado, secao do relatorio e contrato Domínio conhecido; rubrica desconhecida permanece em `unclassified_monetary`.
- `gross_total`, `net_total` e `raw_text` persistido nao podem preencher historico monetario faltante para Fator R.
- `employer_cpp_observed` e `fgts_observed` representam valores observados no relatorio, nao prova de recolhimento efetivo.
- O enrichment historico reutiliza os PDFs originais locais e localiza o import canonico por `organization_id + file_sha256`, sem criar imports, evidencias ou novos periodos.
- A idempotencia do enrichment e medida por igualdade material do `rubrics_summary`; segunda execucao identica deve resultar em `movements_updated = 0`.

## S9.4 - Estimativa FS12 e reconciliacao de Fator R

- `fs12_dominio_estimate` e sempre uma estimativa; o Lumen nao persiste `fs12_official`.
- A janela madura usa os doze meses de `source_payroll_competence` anteriores ao PA, sem incluir a folha do proprio PA.
- `RBT12` vem somente de `SittaxApuracaoSnapshot.rbt12`; ausencia nao pode ser reconstruida por soma local de receita.
- `factor_r_percent` Sittax e percentual em pontos e e normalizado para razao Decimal antes de comparar com `Decimal("0.28")`.
- `POTENTIAL` cadastral nao equivale a `EFFECTIVE`; evidencia explicita de Fator R no snapshot Sittax do PA permite `EFFECTIVE`.
- Contratacao de MEI nao e excluida nem incluida genericamente: sem dado estruturado do caso legal especifico, permanece limitacao de cobertura.
- A cobertura historica de Fator R e provada somente por imports Domínio concluídos no escopo canônico `ACTIVE_COMPANIES`; ausencia da empresa em relatório existente e `CONFIRMED_NO_MOVEMENT`, nao relatorio ausente.
- Enquanto nao existir data canonica de abertura ou historico de atividade por competencia, o S9.4 nao infere `SHORT_HISTORY` e nao transforma meses anteriores em zero.
- `total_warnings` do import Domínio soma warnings de relatorio, warnings promovidos ao nivel da empresa, warnings monetarios e warnings de escopo; warnings exclusivamente internos de secao nao entram nesse contador.
- `resumosTributacaoSittax` nao e promovido a Anexo III/V sem campo ou texto explicito de anexo. A presenca do payload permanece observada, mas nao gera `ANNEX_REVIEW` por inferencia.
