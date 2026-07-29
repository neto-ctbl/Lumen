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
- `S9.4`: API, watcher, frontend e E2E

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
