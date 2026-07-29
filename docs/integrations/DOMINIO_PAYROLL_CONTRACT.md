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
