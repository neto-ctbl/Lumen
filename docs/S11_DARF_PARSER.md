# S11.1-B — Parser documental DARF/SENDA

Stage concluido e validado em 2026-09-16. Escopo exclusivo de guias federais ordinarias em PDF textual; familia `DARF`, tributos derivados da composicao. Nao implementa parcelamentos, guias estaduais/ISS, declaracoes, documentos XML/ZIP, OCR, backfill, reconciliacao ou UI.

## Arquitetura e autoridade

`guide_common.py` concentra leitura PDF textual em modo layout, normalizacao de texto, moeda e validacao estrutural de CNPJ/CPF. DAS e DARF reutilizam essas primitivas. `FederalRevenueGuideExtractor` recebe texto e extrai cabecalho, receitas e validacoes sem decidir familia ou tributo; pode ser reutilizado pelo futuro parser de parcelamento federal mesmo quando DARF rejeita o shell. `darf_tax_codes.py` identifica tributos separadamente. `DarfPdfParser` (`lumen.darf-pdf`, versao `1`) classifica, segmenta e produz resultado tipado.

O registry explicito inclui DAS e DARF. O construtor vazio do runtime continua vazio; polling e backfill continuam desacoplados. Nenhum endpoint, tabela, coluna ou migration foi necessario: o schema existente ja aceita `structured_data` JSON e sinais com proveniencia. Dados permanecem exclusivamente em `fiscal_document_parser_runs`, com idempotencia tenant+evidence+parser+versao; nao preenchem empresa, periodo, imposto, obrigacao, valores, vencimento ou confidence canonicos de `FiscalEvidence`.

A autoridade permanece `CONTENT > FILE_STRUCTURE > FILENAME > PATH`. `supports()` nao consulta filename ou pasta: exige titulo `Documento de Arrecadacao de Receitas Federais`, secao de composicao, todos os rotulos `Codigo`, `Denominacao`, `Principal`, `Multa`, `Juros`, `Total` e pelo menos dois rotulos entre periodo, vencimento, numero documental, pagar ate e total documental. SENDA/Sicalc e contexto observado, nao marcador unico obrigatorio.

Exclusoes anteriores ao aceite: palavras documentais PGFN, SISPAR, PARCSN, PARC, PARCELAMENTO, PARCELA, PERT, RELP, SIMEI, denominacoes de divida ativa e shell Simples Nacional. Nao se identifica o programa ou se interpreta parcelamento. A regressao conjunta exige `supports()` correto para cada parser, tambem com ordem invertida no registry.

O DAS foi endurecido para excluir PARCSN/SIMEI isolados nas observacoes e bundles mistos com titulo federal. A alteracao material exige versao `2`, conforme a decisao de versionamento das runs; versao `1` permanece historica e nao e sobrescrita. As primitivas compartilhadas nao alteram normalizacao ou extracao dos DAS ordinarios.

## Contrato tipado: arquivo nao e sinonimo de guia

`DarfFile.documents[] -> DarfDocument(header, revenues[], validation, page_numbers, block_numbers, warning_codes)`.

- Um DARF unificado: um documento, N receitas, um cabecalho/total.
- PDF com guias independentes: N documentos, cada qual com cabecalho, receitas, total e validacao proprios. Nunca somar totais entre guias para simular um documento unificado.
- Canhoto de pagamento repete titulo, mas nao tem composicao: nao vira segunda guia.
- Blocos com numero documental explicito e cabecalho normalizado identico podem compartilhar identidade em continuacao. Receitas identicas em bloco repetido nao sao somadas novamente, mas paginas/blocos sao preservados e ha warning. Numero igual com cabecalhos diferentes nao permite merge e gera warning.
- Sem numero, nao se presume continuidade. Pagina desconhecida/sem texto em bundle ou familias mistas provoca `UNSUPPORTED` conservador em vez de descartar pagina silenciosamente. Continuacoes sem titulo/cabecalho repetido nao sao suportadas nesta versao.
- Limites: ate 64 blocos com composicao e resultado ate 60.000 bytes antes dos sinais adicionais do runtime. Excesso vira `INCONCLUSIVE`, sem truncar receitas. O endpoint continua impondo 64 KiB ao payload completo.

`DarfHeader` preserva taxpayer_id, tipo CNPJ/CPF, validade estrutural, nome, assessment_period, observed_header_period, assessment_period_source, due_date, document_number, pay_until, total_amount e declaration_receipt_number quando explicito. Nome, identificadores e valores pertencem somente ao resultado estruturado protegido; nao ao probe ou log.

`DarfRevenue` preserva revenue_code observado (inclusive sufixo quando presente), code_extension, description, detail_description, tax, tax_identification_source, assessment_period, due_date, principal_amount, penalty_amount, interest_amount e total_amount. A extensao de duas posicoes na linha de detalhe tambem e preservada. Campos nao observaveis permanecem nulos.

`DarfValidation` preserva revenues_total_amount, sum_matches_total e pay_until_matches_due_date. Sao validacoes tecnicas, nunca pagamento, validade fiscal ou conciliacao.

## Periodos, codigos e moeda

`GuidePeriod` preserva label, kind (`MONTH`, `QUARTER`, `DATE`, `RANGE`, `UNKNOWN`), month, year, quarter, period_start e period_end quando realmente expressos. Apenas MONTH produz `YYYY-MM`. Trimestre preserva ano/numero, sem inventar mes ou limites de calendario. DATE/RANGE preservam datas explicitas; desconhecido preserva label e warning.

O corpus mostrou cabecalho mensal e receita trimestral em IRPJ/CSLL, e cabecalho com data e receita mensal nas duas guias independentes. As duas representacoes sao preservadas. Havendo consenso explicito de todas as receitas diferente do cabecalho, assessment_period usa esse consenso, observed_header_period guarda o original e assessment_period_source registra `REVENUES_CONSENSUS`; ha `DARF_ASSESSMENT_PERIOD_HEADER_DIFFERS_FROM_REVENUES`. Nao e conversao de data/trimestre por inferencia: o periodo escolhido esta explicitamente na composicao. Sem consenso, cada periodo de receita permanece independente e ha warning. Celula de PA vazia nao pode absorver vencimento de outra coluna/linha.

Sinal `period_from_content` usa lista indexada por documento, incluindo periodo e origem interna. `taxes_from_content` preserva tributos normalizados. Proveniencia e confidence acompanham os sinais; hints de filename/path enviados ao runtime coexistem, sem sobrescrita.

Mapping empirico centralizado, nao catalogo fiscal:

| Codigo-base observado | Tributo |
| --- | --- |
| 8109 | PIS |
| 2172 | COFINS |
| 2089, 5993 | IRPJ |
| 2372, 2484 | CSLL |

Codigo conhecido identifica por `REVENUE_CODE`. Codigo novo nao e descartado: denominacao inequivoca pode identificar por `DESCRIPTION`, com warning de codigo desconhecido; caso contrario `tax=UNKNOWN`. Denominacao contraditoria com codigo conhecido gera warning e preserva ambos os dados observados; o mapping prevalece. Nenhuma identificacao usa filename. O mapping foi extraido dos layouts fornecidos, sem afirmar catalogo oficial completo.

Moeda brasileira usa Decimal e strings decimais JSON-safe, nunca float. Colunas posicionais preservam principal/multa/juros/total e celulas vazias de acrescimos no layout observado. Fallback de quatro valores preserva ordem; dois valores representam principal/total com acrescimos vazios. Tres valores sem colunas confiaveis sao ambiguos: principal/total permanecem, multa/juros nulos e warning, sem deslocamento silencioso. Soma dos totais das receitas e comparada ao total da respectiva guia, com tolerancia de um centavo; divergencia nao rejeita a guia.

## Status, warnings e privacidade

MATCHED significa extracao de DARF ordinario, nao imposto correto, pago, transmitido ou obrigacao cumprida. UNSUPPORTED cobre assinatura fraca, outra familia ou parcelamento; PDF textual ausente e INCONCLUSIVE; corrompido e INVALID; falha inesperada de extracao e ERROR sanitizado. Confidence mede completude e consistencia da extracao, usando a menor qualidade entre documentos do bundle.

Warnings incluem `DARF_*_MISSING`, `DARF_TAXPAYER_ID_INVALID_STRUCTURE`, `DARF_ASSESSMENT_PERIOD_UNPARSED`, `DARF_REVENUE_PERIOD_UNPARSED`, `DARF_ASSESSMENT_PERIOD_MULTIPLE`, `DARF_ASSESSMENT_PERIOD_HEADER_DIFFERS_FROM_REVENUES`, `DARF_REVENUE_AMOUNTS_INCOMPLETE`, `DARF_REVENUE_CODE_UNKNOWN`, `DARF_TAX_CODE_DESCRIPTION_CONFLICT`, `DARF_REVENUE_TOTAL_MISMATCH`, `DARF_PAY_UNTIL_DIFFERS_FROM_DUE_DATE`, `DARF_REPEATED_DOCUMENT_BLOCK`, `DARF_DOCUMENT_NUMBER_CONFLICT` e limites/falhas tecnicas. Nenhum warning inclui valores ou texto real.

`python -m agent.parsers.darf_probe -- <PDF_LOCAL>` executa somente DARF, sem fallback DAS ou registro no backend. Stdout permite familia/status, contagens de documentos/receitas/tributos, tributos normalizados, tipos de periodo, presenca de campos essenciais, consistencia agregada (false se qualquer guia divergir, null se nao conclusiva) e codigos de warning. Nao extrai/persiste barcode, linha digitavel, PIX ou observacao integral; nao imprime path, nome, documento, contribuinte ou moeda. O probe nao importa camada de banco, nao envia HTTP e nao cria evidence/run.

Corpus real permanece fora do repositorio, somente read-only. Fixtures sao construidas dinamicamente com identificadores/nomes/valores sinteticos; nenhum PDF ou texto integral e versionado. Renders temporarios servem apenas a QA visual e sao removidos ao finalizar.

## Validacao

Resultados executados em 2026-09-16:

- Suite exclusiva DARF: 70 casos sinteticos, incluida nas regressoes abaixo; DAS: 17 casos existentes preservados.
- Suite focada final DARF+DAS+runtime+parser runs+Watcher: `159 passed, 1 warning` em `49.14s`.
- Backend completo final: `844 passed, 1 warning` em `183.75s`. Primeira rodada anterior aos dois testes finais: `842 passed` em `199.36s`; primeira suite focada aprovada: `157 passed` em `38.93s`.
- Ruff `backend agent`: aprovado. `git diff --check`: aprovado. Warning backend conhecido: deprecacao Starlette/httpx, sem falha funcional.
- Frontend sem alteracao de UI: typecheck aprovado; build aprovado com 62 modulos em `2.96s`; Playwright `14 passed` em `1.5m`, com banco de teste distinto e credenciais sinteticas. Avisos de NO_COLOR/FORCE_COLOR foram somente informativos.
- Alembic operacional: `20260911_0019 (head)`; nenhuma migration criada. O upgrade executado para E2E foi somente na base descartavel, apos restaurar seu schema removido pelo pytest.
- Status Git: nenhuma entrada PDF/XML/ZIP; nove temporarios de QA removidos (oito renders PNG e um PDF sintetico). PDFs originais nao foram tocados e temporarios podem ser regenerados.
- Mudancas locais preexistentes no teste do coletor Econet, scripts de consulta/probe e relatorio TSV foram preservadas e nao pertencem a este stage. Nenhum commit foi executado.

Os negativos sinteticos iniciais revelaram que DAS `1` ainda aceitava PARCSN e SIMEI isolados nas observacoes. O hardening e a protecao de bundle misto foram versionados como DAS `2`; nao se implementou parser desses programas. Os dois testes finais adicionais impedem confusao entre recibo de 14 digitos e taxpayer ausente e comprovam que filename PIS/hint FILENAME nao altera receita COFINS do conteudo.

Corpus read-only em 2026-09-16 (nomes logicos, sem identificadores reais):

| Layout | Documentos | Receitas | Tributos | Periodo normalizado | Warning |
| --- | --- | --- | --- | --- | --- |
| PIS mensal | 1 | 1 | PIS | MONTH | nenhum |
| COFINS mensal | 1 | 1 | COFINS | MONTH | nenhum |
| IRPJ trimestral | 1 | 1 | IRPJ | QUARTER | header diferente da composicao |
| CSLL trimestral | 1 | 1 | CSLL | QUARTER | header diferente da composicao |
| Duas guias federais em PDF | 2 | 2 | IRPJ, CSLL | MONTH | header DATE e composicao MONTH |
| DARF com duas receitas | 1 | 2 | PIS, COFINS | MONTH | nenhum |

Todos os seis retornaram `family=DARF`, `matched=true`, campos essenciais presentes e soma consistente por guia. CNPJ foi validado estruturalmente sem exibir identificador. Recibo de declaracao explicitamente presente foi extraido somente no resultado protegido, nao no resumo. Nos trimestrais, os meses observados no header continuam preservados, enquanto PA explicita da receita permanece trimestral; nao houve inferencia por filename/path.

Controles: tres DAS reais (normal, filename alternativo e observacao IC) continuam MATCHED no DAS e UNSUPPORTED no DARF. Dois PGFN reais, com shells federal e DAS, retornam sem suporte nos dois parsers, comprovado em `supports()` individual e no probe. Nao foram interpretados parcelamentos.

Prova read-only: SHA-256 dos 11 arquivos permaneceu igual antes/depois; transacao SQL read-only encontrou contagens operacionais identicas: `parser_runs=0`, `evidences=1718`, `events=1`, `obligations=196`. Nenhuma run/evidence criada e nenhum envio HTTP. Revalidacao apos restringir taxpayer a celula rotulada confirmou todos os campos e hashes; recibo de 14 digitos nao pode substituir CNPJ ausente. Layouts foram conferidos visualmente, inclusive as duas paginas das guias independentes; PDF sintetico tambem foi renderizado para QA.

Comandos de regressao backend:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  backend/tests/test_darf_pdf_parser.py `
  backend/tests/test_das_pdf_parser.py `
  backend/tests/test_document_parser_runtime.py `
  backend/tests/test_document_parser_runs.py `
  backend/tests/test_document_parser_runs_migration.py `
  backend/tests/test_watcher_client.py `
  backend/tests/test_watcher_ingest.py `
  backend/tests/test_watcher_reprocess.py `
  backend/tests/test_watcher_scanner.py `
  backend/tests/test_watcher_contract.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend agent
git diff --check
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini current
git status --short | Select-String -Pattern '(?i)\.(pdf|xml|zip)$'
```

O E2E deve rodar separado de pytest (ambos usam a base descartavel). Capturar configuracao sem imprimir credenciais, verificar identidade de banco distinta, sobrescrever DATABASE_URL somente no processo e restaurar no finally. Apos pytest, a base de teste existe mas o schema foi removido: upgrade head nessa base antes do bootstrap E2E. Exemplo:

```powershell
$stageOriginalDb = [Environment]::GetEnvironmentVariable('DATABASE_URL', 'Process')
$stageOriginalEmail = [Environment]::GetEnvironmentVariable('E2E_ADMIN_EMAIL', 'Process')
$stageOriginalPassword = [Environment]::GetEnvironmentVariable('E2E_ADMIN_PASSWORD', 'Process')
$stageTestUrl = & .\.venv\Scripts\python.exe -c "from backend.app.core.config import Settings; from sqlalchemy.engine import make_url; s=Settings(); a,b=make_url(s.database_url),make_url(s.test_database_url); assert (a.host,a.port,a.database)!=(b.host,b.port,b.database); print(s.test_database_url)"
if ($LASTEXITCODE -ne 0) { throw 'Base E2E deve ser distinta da operacional.' }
try {
  $env:DATABASE_URL = $stageTestUrl
  $env:E2E_ADMIN_EMAIL = 'e2e.s11.1b@example.local'
  $env:E2E_ADMIN_PASSWORD = 'SyntheticE2E-S11.1B-2026!'
  .\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
  if ($LASTEXITCODE -ne 0) { throw 'Preparacao E2E falhou.' }
  Push-Location .\frontend
  try {
    npm run typecheck
    if ($LASTEXITCODE -ne 0) { throw 'Typecheck falhou.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Build falhou.' }
    npm run test:e2e
    if ($LASTEXITCODE -ne 0) { throw 'E2E falhou.' }
  } finally { Pop-Location }
} finally {
  $stageRestoreValues = @{
    DATABASE_URL = $stageOriginalDb
    E2E_ADMIN_EMAIL = $stageOriginalEmail
    E2E_ADMIN_PASSWORD = $stageOriginalPassword
  }
  foreach ($stageEntry in $stageRestoreValues.GetEnumerator()) {
    if ([string]::IsNullOrEmpty($stageEntry.Value)) {
      Remove-Item -LiteralPath ('Env:\' + $stageEntry.Key) -ErrorAction SilentlyContinue
    } else {
      [Environment]::SetEnvironmentVariable($stageEntry.Key, $stageEntry.Value, 'Process')
    }
  }
}
```

Em workspace UNC, executar npm pela representacao mapeada do mesmo repo, previamente conferida, pois CMD nao aceita cwd UNC. As credenciais acima sao sinteticas e exclusivas da base descartavel. Nao executar E2E contra o admin operacional nem em paralelo com pytest.

## Observacao operacional — restauracao de ambiente e revalidacao adicional

Na revalidacao da usuaria, o finally anterior deixou `DATABASE_URL` como override vazio no processo PowerShell. Esse valor teve precedencia sobre o `.env` e a consulta Alembic falhou na validacao de Settings com `input_value=''`. Nao era uma migration pendente nem evidencia de administrador apagado. A remocao somente do override vazio recuperou `20260911_0019 (head)`, conforme o anexo de validacao.

Regra para os comandos documentados: capturar variaveis antes do E2E; no finally, remover do ambiente do processo valores anteriormente ausentes/vazios com `Remove-Item Env:\...`, e restaurar os valores nao vazios. Nao depender de `SetEnvironmentVariable(..., $null, 'Process')` nessa sessao para representar ausencia. Aplicar a mesma regra a DATABASE_URL, E2E_ADMIN_EMAIL, E2E_ADMIN_PASSWORD e overrides temporarios de validadores, como LUMEN_STAGE_REAL_CASES. A normalizacao de vazio para ausencia e intencional nesses overrides. Isso nao edita o `.env`, nao altera variaveis persistentes de usuario/maquina e nao executa seed, migration ou escrita no banco operacional. O exemplo E2E acima foi corrigido; nenhum script de runtime foi alterado nesta anotacao.

Recuperacao de uma sessao ja afetada:

```powershell
if ([string]::IsNullOrEmpty($env:DATABASE_URL)) {
  Remove-Item -LiteralPath Env:\DATABASE_URL -ErrorAction SilentlyContinue
}
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini current
if ($LASTEXITCODE -ne 0) { throw 'Consulta Alembic falhou.' }
```

O validador real fornecido na conversa tambem usava `hashlib.file_digest`, indisponivel no Python 3.10.11 deste ambiente. A matriz abortava com mensagem generica VALIDATION_SETUP_ERROR. O validador foi reexecutado pela usuaria com SHA-256 streaming compativel; nao houve alteracao do parser ou necessidade de atualizar Python:

```python
def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()
```

Resultados independentes enviados pela usuaria: foco `159 passed, 1 warning` em `64.37s`; backend `844 passed, 1 warning` em `200.15s`; Ruff/typecheck/build aprovados (62 modulos, `2.93s`); E2E isolado `14 passed` em `1.4m`; diff aprovado, sem PDF/XML/ZIP no status. Controles reais DAS com filename alternativo e PGFN federal retornaram UNSUPPORTED no probe DARF, com hashes iguais. Alembic final foi recuperado no head somente apos limpar o override vazio.

A matriz adicional de seis PDFs foi efetivamente executada apos corrigir o hash, mas retornou `REAL_DARF_VALIDATION=FAIL`: quatro casos PASS (IRPJ trimestral, PIS mensal, COFINS mensal e DARF unificado) e dois casos FAIL contra as expectativas do validador:

- Caso logico DUAS_GUIAS_PIS_COFINS: resultado MATCHED com um documento, duas receitas, PIS/COFINS e soma consistente; expectativas de duas guias produziram DOCUMENT_COUNT_MISMATCH e INDEPENDENT_GUIDES_NOT_SEPARATED.
- Caso logico CSLL_MENSAL: resultado MATCHED com periodo MONTH e soma consistente, mas o mes extraido diferiu da expectativa, produzindo MONTH_MISMATCH; houve DARF_ASSESSMENT_PERIOD_HEADER_DIFFERS_FROM_REVENUES.

Todos os seis preservaram hashes, campos essenciais e somas consistentes. Contagens antes/depois identicas: 0 parser runs, 1718 evidences, 1 evento e 196 status de obrigacao. As duas divergencias exigem conferencia do conteudo antes de atribuir falha ao parser ou corrigir expectativas; filename/path nao sao autoridade para decidir mes ou quantidade documental. Nenhum PDF foi aberto nesta anotacao documental, nenhuma expectativa foi relaxada e nenhum dado fiscal sensivel foi copiado. O fechamento anterior refere-se ao corpus inicial; esta revalidacao ampliada permanece com duas pendencias, sem aprovacao integral ou reabertura de etapas futuras.

A sequencia do S11.1 e A DAS, B DARF/SENDA, C estaduais, D ISS, E parcelamentos: parcelamentos ficam depois das guias-base porque reutilizam layouts DAS, federal e estadual. C/D/E, S11.2/S11.3, S12 e backfill nao foram iniciados.

```text
S11.1_B_DARF_CONCLUIDO = YES
PIS_REAL_VALIDATED = YES
COFINS_REAL_VALIDATED = YES
IRPJ_REAL_VALIDATED = YES
CSLL_REAL_VALIDATED = YES
INSTALLMENT_FALSE_POSITIVE_BLOCKED = YES
DAS_REGRESSION_OK = YES
FEDERAL_LAYOUT_EXTRACTOR_REUSABLE = YES
NEW_MIGRATION_CREATED = NO
S11.1_C_INICIADO = NO
S11.2_INICIADO = NO
S11.3_INICIADO = NO
S12_INICIADO = NO
BACKFILL_REAL_EXECUTADO = NO
```
