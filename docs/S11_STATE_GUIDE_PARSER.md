# S11.1-C — Guias estaduais

Implementacao em 2026-09-17; fechamento integral confirmado em 2026-09-21 com
o controle negativo SEFAZ real. A matriz fail-fast terminou com todos os casos
PASS e `REAL_STATE_GUIDE_VALIDATION=PASS`.

## Layout e arquitetura

Os cinco PDFs fornecidos compartilham o DARE 5.1 do Estado de Goias, Secretaria
da Economia. Primeira via bancaria e segunda via contribuinte na mesma pagina
sao copias de um documento, nao duas guias. A via detalhada traz receita,
qualificador/subcodigo e alineas monetarias. Nao ha suporte generico a toda UF,
todo DARE, GNRE ou outro layout estadual sem corpus e testes especificos.

`StateRevenueGuideExtractor` recebe texto e extrai o shell sem decidir tributo.
`StateGuidePdfParser`, `lumen.state-guide-pdf` versao `1`, exclui parcelamentos e
aplica o classifier separado em `state_revenue_codes.py`. Family `STATE_GUIDE`;
guide kinds `ICMS`, `DIFAL`, `DIFAL_CONSUMPTION_ASSET`, `PROTEGE`, `UNKNOWN`.
Layout, tributo e categoria sao distintos: PROTEGE tem tax STATE_REVENUE.
O extrator podera ser reutilizado por parcelamento SEFAZ no mesmo shell;
extrair estrutura nao autoriza classificar esse documento como guia normal.

## Contrato tipado e campos

`StateGuideFile.documents[]` contem documentos com header, guide_kind,
revenues[], validation, paginas/blocos e warnings. Cada receita conserva
codigo/descricao, codigo/descricao principal quando ha qualificador, tax,
categoria, origem da classificacao e components[] tipados.

Header: CNPJ/CPF rotulado e check digits, IE, contribuinte, UF emissora e UF do
endereco quando explicita, numero, documento de origem, condicao, referencia
original, codigo de periodicidade, periodo semantico, origem do periodo,
vencimento, validade de pagamento, referencia de parcela e total. Ausentes
ficam NULL. Os cinco reais nao exibem CNPJ/CPF; IE/nome nao substituem CNPJ.
GO emissor vem do orgao no conteudo, nunca do filename/endereco/path.

Referencia original e normalizacao ficam separadas. Apenas mes explicito vira
YYYY-MM; trimestre, data, intervalo e referencia desconhecida conservam tipos.
Referencia com codigo/periodicidade e lida como estrutura documental.
`period_from_content` informa CONTENT_REFERENCE; hints de path e filename
fornecidos ao runtime ficam independentes. Pasta nao corrige conteudo;
vencimento e validade nao viram competencia ou mes de geracao.

Valores usam Decimal serializado como string. Componentes preservam rotulo,
codigo da alinea, natureza e valor. Principal/multa/juros so sao preenchidos por
alineas observadas; ausentes ficam NULL, nao zero inventado. Soma comparada ao
total documental; divergencia e warning tecnico, nunca alerta fiscal.

## Mapping empirico

| Codigo | Contexto confirmado | Categoria |
|---|---|---|
| 108 | Qualificador NORMAL sob ICMS, principal 1 | ICMS |
| 4502 | ICMS DIFAL | DIFAL |
| 159 | Diferencial de aliquotas uso/consumo/ativo | DIFAL_CONSUMPTION_ASSET |
| 4014 | Contribuicoes ao PROTEGE | PROTEGE |
| 41 | Qualificador CONTRIBUICAO somente sob 4014 | PROTEGE |

41 isolado nao identifica PROTEGE. Ambos os codigos/descricoes sao preservados;
o qualificador nao cria uma segunda receita. 108 exige contexto ICMS.
Mapping Python e empirico, nao catalogo legal nem tabela/migration. Codigo novo
e conservado com warning. Descricao conclusiva permite fallback DESCRIPTION
com warning; sem conclusao retorna UNKNOWN. Conflito codigo/descricao ou
descricoes contraditorias retorna UNKNOWN. DIFAL sem natureza explicita nao
vira consumo/ativo pelo nome/pasta. Nao se infere modalidade de pagamento.

## Multi-guia, negativos e limites

Guias independentes ficam em documents[] separados, com cabecalhos/totais e
locators proprios. A via bancaria sem tabela so pode ser ignorada quando possui
numero explicito igual a uma via detalhada posterior e total/validade; numero
divergente resulta UNSUPPORTED. Repeticao exata de numero/header/receitas
deduplica componentes e conserva paginas/blocos. Mesmo numero com conteudo
distinto nao e fundido: documentos separados e warning de conflito.
Continuacoes sem estrutura conclusiva e paginas desconhecidas/brancas/mistas
sao UNSUPPORTED conservador. Multi-guia estadual e cobertura sintetica, nao
validacao real: nao houve amostra estadual real multipagina no corpus fornecido.

Parcelamento/acordo ou campo Parcela preenchido excluem guia normal antes do
match. Rotulo Parcela vazio/com hifen do DARE normal nao exclui. Nenhum programa
de parcelamento e identificado. DAS, DARF, PGFN, ISS/municipais e PDFs arbitrarios
sao negativos. supports independente da ordem do registry. Registry explicito
DAS 2 + DARF 1 + STATE_GUIDE 1; construtor vazio permanece vazio. Sem polling.

MATCHED: shell reconhecido, inclusive categoria UNKNOWN com warning;
UNSUPPORTED: excluido/desconhecido; INCONCLUSIVE: sem texto ou nos limites;
INVALID: PDF corrompido; ERROR: falha inesperada sanitizada. Confidence e somente
qualidade documental. Limites: 64 blocos detalhados, 60.000 bytes antes do contexto
runtime (teto backend 64 KiB), sem truncamento silencioso.

## Persistencia e privacidade

Reutiliza fiscal_document_parser_runs, com idempotencia existente. Sem tabela,
migration ou promocao canonica de company/period/tax/obligation/amount/due date.
FiscalEvidence e fiscal_obligation_statuses nao sao alterados. Sem reconciliacao,
backfill, consulta SEFAZ, verificacao de pagamento ou S12. Corpus e texto integral
nao sao versionados; fixtures sinteticas nao contem dados fiscais reais.

Probe estadual-only offline/read-only, sem conexao ao banco:

```powershell
.\.venv\Scripts\python.exe -m agent.parsers.state_guide_probe -- '<PDF_LOCAL>'
if ($LASTEXITCODE -ne 0) { throw 'Probe estadual falhou.' }
```

Stdout allowlisted: family/status/matched, contagens/categorias, codigos conhecidos,
presenca de campos, soma consistente e warnings. Sem CNPJ, IE, nome, valores,
numero, barcode, path ou texto integral. Caminhos abaixo sao placeholders.

## Validador real unico, fail-fast

Suites (pytest usa banco de teste, nunca operacional):

```powershell
.\.venv\Scripts\python.exe -m pytest `
  backend/tests/test_state_guide_pdf_parser.py `
  backend/tests/test_darf_pdf_parser.py `
  backend/tests/test_das_pdf_parser.py `
  backend/tests/test_document_parser_runtime.py `
  backend/tests/test_document_parser_runs.py -q
if ($LASTEXITCODE -ne 0) { throw 'Suite focada falhou.' }
.\.venv\Scripts\python.exe -m pytest backend/tests -q
if ($LASTEXITCODE -ne 0) { throw 'Regressao backend falhou.' }
.\.venv\Scripts\python.exe -m ruff check backend agent
if ($LASTEXITCODE -ne 0) { throw 'Ruff falhou.' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Diff falhou.' }
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini current
if ($LASTEXITCODE -ne 0) { throw 'Consulta Alembic falhou.' }
git status --short | Select-String -Pattern '(?i)\.(pdf|xml|zip)$'
```

```powershell
.\.venv\Scripts\python.exe -m agent.parsers.state_guide_validation `
  --icms '<PDF_ICMS>' `
  --difal '<PDF_DIFAL>' `
  --difal-consumption-asset '<PDF_CONSUMO>' `
  --difal-consumption-asset '<PDF_ATIVO>' `
  --protege '<PDF_PROTEGE>' `
  --das '<PDF_DAS>' `
  --darf '<PDF_DARF>' `
  --sefaz-installment '<PDF_PARCELAMENTO_SEFAZ>'
if ($LASTEXITCODE -ne 0) { throw 'Matriz real estadual falhou.' }
```

Paths sao fornecidos na invocacao, nunca salvos no Git. Consumo/ativo aceita
opcao repetida. SHA-256 streaming Python 3.10 antes/depois, inclusive na falha.
Banco operacional configurado: transacoes READ ONLY antes/depois, contagens e
fingerprints internos das linhas de runs/evidences/events/statuses/users, mais
Alembic. Fingerprints/credenciais nao sao impressos. Detecta mutacoes com mesma
contagem, inclusive de admin/campos canonicos. Probe/parser normais nao importam
backend nem criam engine. Nenhuma escrita/seed/migration operacional.

Na primeira falha nao executa casos posteriores, emite codigo sanitizado e
exit 1; argumentos invalidos retornam 2 sem ecoar paths. Ausencia de amostra,
inclusive negativo SEFAZ, e falha, nunca PASS ficticio. PASS anteriores a falha
valem somente para esses casos; resultado global e FAIL.

## Resultados reais em 2026-09-17 e fechamento em 2026-09-21

Conferencia visual read-only das cinco paginas confirmou DARE_GO_5_1. Todos os
cinco positivos reconhecidos (ICMS, DIFAL, dois consumo/ativo, PROTEGE), com campos
essenciais disponiveis e somas consistentes. TAXPAYER_ID_MISSING esperado, porque
CNPJ/CPF nao consta no shell. Um DAS e um DARF reais preservaram familias/status
e nao foram capturados pelo estadual. SHA-256 dos sete originais inalterado.

Banco: 0 runs, 1718 evidences, 1 evento, 196 status de obrigacao e 3 users;
snapshot final com fingerprints internos inalterado. Alembic 20260911_0019 (head).

Na primeira rodada nao havia PDF de parcelamento SEFAZ nas fontes delimitadas;
o validador corretamente retornou SAMPLE_MISSING/FAIL. Uma amostra real foi
fornecida depois: ela compartilha o shell DARE 5.1, possui marcadores explicitos
de parcelamento/celula preenchida e permaneceu UNSUPPORTED no parser estadual
normal. Hash e snapshot de banco permaneceram iguais. A matriz final registrou
ICMS, DIFAL, DIFAL_CONSUMO_ATIVO, PROTEGE, DAS_REGRESSION, DARF_REGRESSION e
SEFAZ_INSTALLMENT_NEGATIVE como PASS e terminou com
`REAL_STATE_GUIDE_VALIDATION=PASS`.

Suíte estadual: 71 testes sinteticos. Backend completo da ultima versao:
915 passed, 1 warning conhecido Starlette/httpx em 189.72s. Uma execucao parcial
anterior sofreu interferencia de outra suite na mesma base descartavel, foi
interrompida e descartada; nenhum resultado parcial foi usado como validacao.
A repeticao completa ocorreu sequencialmente e passou. Nunca executar dois
pytest com fixtures de banco nem pytest/E2E simultaneamente sobre lumen_test.
Foco inicial com Watcher: 225 passed em 44.19s, antes dos quatro casos finais de
robustez. Foco final integrado estadual/DAS/DARF/runtime/runs/Watcher:
229 passed, 1 warning em 50.53s. Playwright existente: 14 passed em 1.3m,
banco lumen_test e admin sintetico exclusivos. Snapshot operacional de todas
as cinco tabelas (contagens e fingerprints internos) identico antes/depois do
E2E, incluindo users; nenhum admin operacional foi criado/alterado/apagado.
Env restaurado removendo overrides antes ausentes/vazios, sem editar .env.
Ruff e diff aprovados. Frontend typecheck/build: 62 modulos, 2.76s.
Checagens do validador tambem permanecem ativas em python -O/PYTHONOPTIMIZE;
guard otimizado validado, nao depende de assert removivel pelo interpretador.
Nenhuma UI nova. E2E separado do operacional, admin sintetico; nao rodar junto
com pytest. Restaurar env removendo overrides antes ausentes/vazios e restaurando
somente valores nao vazios, conforme S11_DARF_PARSER.

Ordem S11.1: A DAS, B DARF/SENDA, C estaduais, D ISS, E parcelamentos. SEFAZ futuro
reutilizara shell estadual quando compativel. D/E, S11.2/S11.3, S12 e backfill nao
iniciados. Sem migration nova; head preservado 20260911_0019.

Git status final sem PDF/XML/ZIP; cinco renders QA temporarios removidos. Nenhum
commit/staging realizado. Alteracoes preexistentes de outros trabalhos e do
S11.1-B preservadas; nao incluir indiscriminadamente o worktree em commit.
Os tres blocos PowerShell deste documento passaram no parser sintatico, sem
executar placeholders. Ruff e git diff --check finais aprovados.

```text
S11.1_C_STATE_GUIDES_CONCLUIDO = YES
ICMS_REAL_VALIDATED = YES
DIFAL_REAL_VALIDATED = YES
DIFAL_CONSUMO_ATIVO_REAL_VALIDATED = YES
PROTEGE_REAL_VALIDATED = YES
SEFAZ_INSTALLMENT_NEGATIVE_VALIDATED = YES
DAS_REGRESSION_OK = YES
DARF_REGRESSION_OK = YES
STATE_LAYOUT_EXTRACTOR_REUSABLE = YES
NEW_MIGRATION_CREATED = NO
S11.1_D_INICIADO = NO
S11.2_INICIADO = NO
S11.3_INICIADO = NO
S12_INICIADO = NO
BACKFILL_REAL_EXECUTADO = NO
```
