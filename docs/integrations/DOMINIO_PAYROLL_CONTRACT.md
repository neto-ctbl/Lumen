# Domínio Payroll Contract

## 1. Objetivo

Congelar o contrato documental do `Resumo Mensal` da Domínio Folha para o S9.0, sem parser completo, sem banco e sem endpoint.

## 2. Arquitetura

```text
Domínio Folha
    ↓
coletor Windows opcional
    ↓
Resumo Mensal da Folha em PDF
    ↓
upload manual ou watcher
    ↓
parser offline do Lumen
    ↓
movimento por empresa
    ↓
origem da DCTFWeb e sinais de folha
```

O núcleo do Lumen não depende de automação de tela. O coletor Windows é opcional e desacoplado de FastAPI, worker Docker, banco, frontend e request HTTP.

## 3. Fonte documental

- fonte principal do S9: PDF `Resumo Mensal` da folha;
- o PDF é evidência documental de movimento;
- o PDF não é fonte principal de cadastro;
- o PDF não é fonte principal de regime;
- o PDF não é fonte principal de CNAE;
- o PDF não prova sozinho entrega de DCTFWeb;
- upload manual continuará suportado.

## 4. Campos observados no PDF

Campos previstos para os stages futuros:

- `dominio_company_code`
- `company_cnpj`
- `company_name`
- `source_payroll_competence`
- `assessment_competence`
- `calculation_type`
- `source_pages`
- `raw_text`
- `has_payroll`
- `has_employee`
- `has_pro_labore`
- `has_autonomous`
- `has_inss`
- `has_fgts`
- `has_termination`
- `has_vacation`
- `has_leave`
- `gross_total`
- `discount_total`
- `informative_total`
- `net_total`

## 5. Estrutura por empresa

O contrato observado considera blocos por empresa, com identificação própria, CNPJ, competência da folha e sinais de movimento que poderão ocupar uma ou mais páginas.

## 6. Páginas múltiplas

O parser futuro deve suportar:

- empresas com `1/2`, `2/2`;
- agrupamento por empresa;
- cabeçalhos repetidos;
- páginas de continuação;
- páginas de continuação vazias.

## 7. Blocos complementares

O contrato precisa tolerar blocos como:

- `Folha Mensal`;
- alterações salariais;
- lançamentos complementares;
- combinações de blocos na mesma empresa.

## 8. Rubricas

Rubricas serão tratadas no parser offline do S9.1. O S9.0 apenas congela cenários sintéticos com sinais observáveis de folha.

## 9. Totais

Os totais futuros permanecerão no contrato, mas ainda sem persistência:

- `gross_total`
- `discount_total`
- `informative_total`
- `net_total`

Valores seguem notação brasileira e não devem ser inferidos por locale do sistema.

## 10. Limitações

- S9.0 não implementa parser completo;
- S9.0 não implementa OCR;
- S9.0 não implementa migration;
- S9.0 não implementa persistência;
- S9.0 não implementa API;
- S9.0 não implementa watcher do backend;
- S9.0 não implementa frontend.

## 11. Regra folha M → apuração M+1

Esta regra é obrigatória e definitiva:

```text
source_payroll_competence != assessment_competence
```

Ambas são obrigatórias.

Exemplo obrigatório:

```text
Relatório Domínio:
Competência da folha = 05/2026

Lumen:
source_payroll_competence = 2026-05
assessment_competence = 2026-06
```

Exemplo de rollover:

```text
source_payroll_competence = 2026-12
assessment_competence = 2027-01
```

No futuro:

- `period_id` apontará para a competência de apuração;
- a competência original da folha continuará armazenada separadamente;
- nunca haverá alteração silenciosa da competência do relatório.

## 12. Impacto em DCTFWeb

- o PDF prova movimento, não entrega;
- `Domínio Folha somente = DP`;
- `REINF somente = FISCAL`;
- `MIT/federal somente = FISCAL`;
- `Domínio Folha + REINF/MIT = COMPARTILHADO`;
- folha `M` produz efeitos na apuração `M+1`.

## 13. Impacto em Fator R

O PDF é fonte de sinais de folha para análise futura de Fator R. Ausência de sinal no arquivo não equivale a evidência negativa conclusiva.

## 14. Segurança

- fixtures são 100% sintéticas;
- nomes reais de empresa não entram em fixture;
- CNPJs reais não entram em fixture;
- `.env` e credenciais ficam fora do Git;
- PDF real e log real não entram no repositório.

## 15. Idempotência

O coletor Windows do S9.0 usa:

- SHA-256 do PDF definitivo;
- escrita temporária `.partial.pdf`;
- `os.replace(...)` para troca atômica;
- manifest lateral atômico;
- lock local por arquivo;
- retry explícito e limitado na exportação.

## 16. Fixtures sintéticas

Os cenários sintéticos congelados no S9.0 cobrem:

- somente pró-labore;
- empregado + INSS + FGTS;
- autônomo;
- férias;
- rescisão;
- afastamento;
- empresa com duas páginas;
- continuação vazia;
- alteração salarial;
- múltiplos blocos;
- CNPJ inválido;
- competência inválida;
- `05/2026 -> 06/2026`;
- `12/2026 -> 01/2027`.

## 17. Fronteiras dos micro-stages

- `S9.0`: contrato, segurança, fixtures, helper de competência e coletor Windows opcional
- `S9.1`: parser offline do PDF
- `S9.2`: persistência, importador e matching
- `S9.3`: origem DCTFWeb, departamentos e alertas
- `S9.4.0`: enriquecimento monetario estruturado do historico
- `S9.4`: FS12 estimado, RBT12 Sittax e reconciliacao de Fator R
- `S9.5`: API, watcher, frontend e E2E

## 18. Critérios de aceite

- contrato puro e sem banco;
- regra `folha M -> apuração M+1` inequívoca;
- fixtures sintéticas;
- coletor Windows com lock, retry, validação mínima, SHA-256 e manifest;
- nenhum PDF real, log real ou credencial no Git;
- apenas S9.0 implementado.

## 19. Complemento do S9.1

O S9.1 materializa o parser offline puro do `Resumo Mensal` com:

- `parse_dominio_payroll_pdf(path: Path) -> DominioPayrollReport`
- `parse_dominio_payroll_pages(pages: Sequence[str], *, source_file_name: str = "<memory>") -> DominioPayrollReport`

Decisao tecnica do S9.1:

- `pypdf` e o extrator primario do PDF textual;
- OCR permanece fora do caminho principal;
- `PyMuPDF` aparece apenas no teste sintetico de fronteira para gerar PDF temporario.

## 20. Regras materializadas no parser

O parser do S9.1:

- separa leitura do arquivo da interpretacao textual;
- agrupa empresa por `codigo Dominio + CNPJ normalizado + competencia original da folha`;
- preserva blocos `MONTHLY_PAYROLL`, `SALARY_ADJUSTMENT`, `PAYMENT_ENTRY`, `COMPLEMENTARY` e `UNKNOWN`;
- preserva secoes `EARNINGS`, `DEDUCTIONS` e `INFORMATIONAL`;
- parseia rubricas da direita para a esquerda;
- normaliza dinheiro em `Decimal`, inclusive `,95`;
- normaliza horas em minutos, inclusive `220:00` e `7:20`;
- preserva marcador `*`;
- extrai totais declarados e `Liquido Geral`;
- gera warnings estruturados e excecoes de dominio proprias;
- preserva origem dos sinais em `signal_sources`.

Regra semantica consolidada no fechamento do S9.1:

- `INSS EMPREGADOR` e sinal de `has_inss`, mas nao prova `has_employee`;
- `PRO-LABORE` e `AUTONOMO` continuam podendo gerar `has_pro_labore` e `has_autonomous`, mas nao sao classificados como empregado por si sos;
- `has_employee` depende apenas de rubricas inequivocamente trabalhistas, por codigo conhecido ou nome normalizado equivalente;
- `signal_sources["has_employee"]` nao deve ser explicado apenas por `100`, `9380`, `235`, `843`, `858` ou `856`.

## 21. Validacao real agregada do S9.1

Validacao local agregada executada em 2026-07-29, sem expor nomes, CNPJs ou `raw_text`:

- `Resumo_Mensal_05-2026.pdf`
  - `149` paginas fisicas
  - `137` empresas identificadas
  - `employee_true = 90`
  - `employee_false = 47`
  - `pro_labore_without_employee = 47`
  - `autonomous_without_employee = 5`
  - `employee_only_supported_by_forbidden_codes = 0`
  - competencias de folha: `2026-05`
  - competencias de apuracao: `2026-06`
  - warnings agregados por empresa: `CONTINUATION_PAGE_EMPTY = 1`, `SECTION_TOTAL_MISMATCH = 7`
  - tempo observado: `3.423s`
- `Resumo_Mensal_06-2026.pdf`
  - `145` paginas fisicas
  - `137` empresas identificadas
  - `employee_true = 90`
  - `employee_false = 47`
  - `pro_labore_without_employee = 47`
  - `autonomous_without_employee = 5`
  - `employee_only_supported_by_forbidden_codes = 0`
  - competencias de folha: `2026-06`
  - competencias de apuracao: `2026-07`
  - warnings agregados por empresa: `CONTINUATION_PAGE_EMPTY = 1`, `SECTION_TOTAL_MISMATCH = 3`
  - tempo observado: `3.840s`

## 22. Limitacoes conhecidas apos o S9.1

- o parser continua offline e sem persistencia;
- o parser nao faz matching com cadastro local;
- o parser nao decide responsabilidade final da DCTFWeb;
- o parser nao executa OCR;
- o parser nao expoe endpoint HTTP;
- o parser nao grava banco nem aciona watcher;
- rubricas novas podem exigir ampliacao futura do catalogo classificatorio.

## 23. Materializacao do S9.2

O S9.2 fecha a trilha de persistencia offline do Dominio com:

- migration `20260730_0012_create_dominio_payroll_tables.py`;
- tabelas `dominio_payroll_imports` e `dominio_payroll_company_movements`;
- importador `import_dominio_payroll_file(...)`;
- matching por `organization_id + cnpj`;
- idempotencia por `organization_id + file_sha256`;
- `source_payroll_competence` e `assessment_competence` persistidas separadamente;
- `fiscal_period_id` sempre resolvido pela competencia de apuracao `M+1`;
- `rubrics_summary` deterministico em JSONB;
- `fiscal_evidences` apenas para movimentos `MATCHED`;
- `integration_sync_runs` e `audit_log` para import real;
- CLI `backend/scripts/import_dominio_payroll.py` com `--dry-run`.

Regras mantidas:

- `INSS EMPREGADOR` continua sendo prova de `has_inss`, nao de `has_employee`;
- pro-labore e autonomo nao sao classificados como empregado por si sos;
- o PDF nao marca obrigacao como entregue;
- o S9.2 nao define `DP`, `FISCAL` ou `COMPARTILHADO`;
- o S9.2 nao cria watcher, endpoint HTTP, tabela de rubricas, alertas ou frontend.

## 24. Addendum S9.2

- `dominio_payroll_imports` passa a registrar `selection_scope`, `source_filter_name`, `target_company_count` e `target_list_sha256`.
- Manifest legado com `selection_scope = ATIVAS` deve ser normalizado para `ACTIVE_COMPANIES`, preservando o valor original em `raw_metadata`.
- Manifest sem `selection_scope`, mas com `source_filter_name = Ativas`, deve ser inferido como `ACTIVE_COMPANIES`.
- Manifest sem `selection_scope`, mas com `source_filter_name = Fator R`, deve ser inferido como `FACTOR_R`.
- Importacao sem manifest continua permitida com `selection_scope = UNKNOWN`.
- O stage adiciona apenas preparacao operacional e documental do universo `FACTOR_R`.
- O exportador read-only `backend/scripts/export_dominio_factor_r_targets.py` gera CSV local e resumo JSON sem identificadores reais.
- O collector Windows aceita `--company-filter` para reaproveitar filtros operacionais ja existentes no Dominio.
- O collector mensal canonico do Lumen usa `--company-filter "Ativas"` e um PDF por competencia.
- `target_company_count` e `target_list_sha256` pertencem somente ao escopo `FACTOR_R`; imports `ACTIVE_COMPANIES`, `CUSTOM` e `UNKNOWN` devem persistir esses campos como `null`.
- O filtro `Fator R` e o modo intervalo permanecem opcionais para auditoria, diagnostico ou contingencia; a janela historica de 12 meses deve ser montada a partir dos movimentos persistidos.
- O S9.2 nao calcula percentual do Fator R, nao estima anexo final, nao gera alertas persistidos e nao cria divergencia fiscal.

## 25. Materializacao do S9.3

O S9.3 deriva origem e responsabilidade operacional esperadas da DCTFWeb, por empresa e competencia de apuracao, sem alterar o status fiscal da obrigacao:

- import `ACTIVE_COMPANIES` e movimento matched da competencia de apuracao confirmam cobertura DP;
- import `ACTIVE_COMPANIES` sem movimento da empresa confirma ausencia observada de movimento, sem afirmar ausencia juridica de DP;
- falta de import mensal canonico e `REPORT_MISSING`, nunca ausencia de DP;
- sinais de empregado, pro-labore, autonomo, INSS, rescisao, ferias ou afastamento provam componente DP; FGTS isolado e apenas suporte;
- DCTFWeb e tratada operacionalmente como eSocial + EFD-Reinf + MIT: eSocial/Domínio compoe DP; REINF/MIT compoem Fiscal;
- `REINF` canonica e sinal Fiscal apenas quando a obrigacao/evidencia for explicitamente `REINF`;
- MIT e sinal Fiscal apenas a partir da PA `2025-01` e, no catalogo atual, apenas por `PIS` e `COFINS`; DAS, regime tributario e `EFD_CONTRIBUICOES` nao inferem MIT;
- Domínio + REINF/MIT resulta em `COMPARTILHADO`; Fiscal com ausencia DP confirmada resulta em `FISCAL`; Fiscal com cobertura Domínio ausente resulta em `UNDETERMINED`;
- empresa atualmente ativa sem DP, REINF, MIT ou DCTFWeb observados fica `UNDETERMINED` com `NO_DCTFWEB_COMPONENT_OBSERVED`, sem alerta;
- observacao de DCTFWeb por status, evidencia ou entrega Acessorias canonicamente mapeada e distinta de entrega confirmada e nao determina origem sozinha;
- origem esperada e departamento esperado nao substituem `fiscal_obligation_statuses` ou conciliacao final.

## 26. Materializacao do S9.4.0

O S9.4.0 prepara a trilha Dominio para o Fator R sem calcular ainda `FS12` ou reconciliacao fiscal:

- `rubrics_summary` evolui internamente para `schema_version = 2` sem migration de banco;
- os campos do S9.2 (`codes`, `signals`, `blocks`, `rubric_count`) permanecem preservados por compatibilidade;
- cada movimento passa a carregar `monetary_categories`, `monetary_summary_confidence`, `unclassified_monetary` e `excluded_monetary`;
- os valores monetarios nascem do parser estruturado do PDF original, usando `Decimal` do inicio ao fim;
- `gross_total`, `net_total` e `raw_text` persistido nao podem ser usados como atalho para preencher historico monetario;
- o stage diferencia explicitamente `employee_remuneration`, `pro_labore`, `autonomous`, `thirteenth_salary`, `employer_cpp_observed` e `fgts_observed`;
- rubrica monetaria nao classificada cai obrigatoriamente em `unclassified_monetary` com warning estruturado `UNCLASSIFIED_MONETARY_RUBRICS`;
- `employer_cpp_observed` e `fgts_observed` representam valor observado no relatorio, nao comprovacao de recolhimento.

Schema resumido observado no `rubrics_summary` v2:

```json
{
  "schema_version": 2,
  "codes": [],
  "signals": {},
  "blocks": [],
  "monetary_summary_confidence": "COMPLETE|PARTIAL|INSUFFICIENT",
  "monetary_categories": {
    "employee_remuneration": {"amount": "0.00", "rubric_count": 0},
    "pro_labore": {"amount": "0.00", "rubric_count": 0},
    "autonomous": {"amount": "0.00", "rubric_count": 0},
    "thirteenth_salary": {"amount": "0.00", "rubric_count": 0},
    "employer_cpp_observed": {"amount": "0.00", "rubric_count": 0},
    "fgts_observed": {"amount": "0.00", "rubric_count": 0}
  },
  "unclassified_monetary": {"amount": "0.00", "rubric_count": 0},
  "excluded_monetary": {"amount": "0.00", "rubric_count": 0}
}
```

Fechamento operacional validado em 2026-08-21:

- enrichment real do backfill `07/2025` a `06/2026` por reprocessamento dos `12` PDFs locais originais;
- `1624` movimentos pareados `1:1` e enriquecidos para `schema_version = 2`;
- segunda execucao idempotente com `movements_updated = 0`;
- nenhuma nova linha de import, nenhuma nova `fiscal_evidence` e nenhuma alteracao de matching.
