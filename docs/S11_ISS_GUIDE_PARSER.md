# S11.1-D — Parser documental de guias de ISS municipal

Status: concluído em 2026-09-22. Parser `lumen.iss-guide-pdf`, versão `1`.
Nenhuma migration, tabela, endpoint, UI, polling, backfill ou promoção canônica foi criada.

## Auditoria do corpus

A auditoria read-only partiu de 70 candidatos operacionais por nome/contexto e
inspecionou texto e renderização das variantes. O nome e o path foram usados somente
para localizar candidatos; nenhuma classificação depende deles. Foram comprovados
dois layouts físicos de guia:

- `ANAPOLIS_DUAM`: Documento Único de Arrecadação Municipal da Prefeitura de
  Anápolis, com bloco do pagador e grade de lançamento/principal/correção/juros/multa/total;
- `NEROPOLIS_DUAM`: DUAM da Prefeitura de Nerópolis, com dados do econômico,
  referência/parcela/emissão/vencimento/validade e grade de tributo/base/alíquota/componentes.

Nenhum dos layouts anteriores (`DAS_FORM`, `FEDERAL_REVENUE_FORM`, `DARE_GO_5_1`)
representa esses formulários. Portanto, os dois novos IDs estruturais foram necessários.
O corpus também contém relatórios de acompanhamento/NFS-e e carta de lembrete de
débitos; esses documentos foram tratados como negativos, não como guias normais.

Anápolis contém amostras reais `ISS_OWN` e `ISS_WITHHELD` no mesmo layout. A diferença
vem da descrição do lançamento (`próprio` versus `retido`), confirmando que layout e
modalidade fiscal são dimensões separadas. Nerópolis confirmou uma segunda variante
real de `ISS_OWN`.

## Pipeline e contrato

O parser usa deliberadamente:

```text
Detect Layout -> Extract -> Classify -> Parser Result
```

`AnapolisDuamExtractor` e `NeropolisDuamExtractor` implementam o contrato estrutural.
`IssGuideClassifier` recebe apenas `IssLayoutExtraction` e não reabre o PDF.
`IssGuidePdfParser` compõe os dois pipelines por `ComposableDocumentParser`. Para
permitir classificação por documento, o composable ganhou o callback retrocompatível
`serialize_result(extracted, classification)`; parsers existentes continuam usando
`serialize_extracted`. `DocumentParserRuntime` não mudou.

O resultado tipado é `IssGuideFile.documents[]`, com:

- `header`: layout, CNPJ/CPF e validade estrutural, inscrição municipal, nome,
  município/UF, referência, período normalizado e proveniência, emissão, vencimento,
  validade, número da guia, identificador municipal e total;
- `classification`: `ISS_OWN`, `ISS_WITHHELD` ou `UNKNOWN`, confiança e fonte;
- `revenues[]`: código e descrição bruta quando presentes, lançamento municipal,
  base, alíquota e componentes `Decimal`;
- `validation`: total calculado e comparação com o total documental;
- localizadores de página/bloco e warnings sanitizados.

O conteúdo produz `period_from_content`; qualquer `period_from_path` recebido continua
separado no contexto e não sobrescreve o período documental. Campo ausente permanece
`NULL`. Confidence mede leitura/classificação, não pagamento, correção ou regularidade.

## Classificação, códigos e limites

- `ISS_OWN`: somente marcador textual explícito de ISS próprio/prestador;
- `ISS_WITHHELD`: somente marcador explícito de ISS retido/retenção/tomado;
- `UNKNOWN`: layout conhecido sem sinal conclusivo; estrutura permanece `MATCHED` e preservada;
- código municipal `002`: comprovado no layout Nerópolis e preservado;
- qualquer outro código: preservado com `ISS_MUNICIPAL_REVENUE_CODE_UNKNOWN`;
- parcelamento/acordo/carta de cobrança inequívoca: `UNSUPPORTED`, reservado ao S11.1-E;
- novo formulário municipal: `UNKNOWN_GUIDE_LAYOUT`/`UNSUPPORTED` até existir amostra e extractor;
- NFS-e, relatório, declaração ou mero texto com ISS não satisfaz a assinatura de arrecadação.

Os detectores exigem combinações fortes de órgão emissor, título DUAM e grade física.
Não existe parser municipal universal nem catálogo municipal em banco.

## Probe e validação

`agent.parsers.iss_guide_probe` imprime apenas agregados allowlisted: família, layout,
status, quantidade, classificações, presença de campos, quantidade de componentes,
validação de soma e códigos de warning. Nunca imprime path, texto, nomes, documentos,
inscrições, números de guia ou valores.

`agent.parsers.iss_guide_validation` é fail-fast e read-only. Ele compara SHA-256 antes
e depois de cada amostra, snapshot e fingerprint das tabelas operacionais antes/depois,
e confirma o head `20260911_0019`. A execução real aprovada cobriu:

- Anápolis próprio e retido, comprovando o mesmo layout;
- Nerópolis próprio;
- relatório municipal/NFS-e-like como negativo;
- regressões reais DAS, DARF e DARE estadual;
- parcelamento SEFAZ como negativo;
- banco e arquivos inalterados, sem parser run ou evidence criados.

Resultado: `REAL_ISS_GUIDE_VALIDATION=PASS`. A suíte focada encerrou com
`212 passed, 1 warning` e o backend completo com `951 passed, 1 warning`; o warning
conhecido é a depreciação Starlette/httpx. Ruff, typecheck, build (62 módulos),
Playwright isolado em `lumen_test` (`14 passed`), `git diff --check` e Alembic
`20260911_0019 (head)` também foram aprovados. A tentativa inicial de typecheck por
UNC foi descartada porque o `cmd.exe` do npm não preserva diretório UNC; a execução
válida ocorreu pela unidade mapeada `G:`.

### Revisão das quatro amostras fornecidas após o fechamento

As quatro amostras adicionais foram renderizadas e inspecionadas integralmente. Elas
confirmaram três guias Anápolis e uma Nerópolis; nenhum terceiro layout foi necessário.
A revisão revelou e corrigiu duas variações da camada de texto de Anápolis: espaço ao
redor do hífen no cabeçalho/CNPJ e modalidade `Próprio` quebrada na linha seguinte.

A guia atualizada comprovou ainda que um DUAM pode reunir vários lançamentos, cada qual
com competência e vencimento próprios. `IssRevenue` passou a preservar
`reference_label`, `reference_period`, sua proveniência e `due_date`. Quando há mais de
uma competência, o header não escolhe arbitrariamente uma delas: seu período fica
`NULL`, as competências permanecem nas receitas e o resultado emite
`ISS_MULTIPLE_REFERENCE_PERIODS`. A sonda confirmou três receitas, três períodos e
soma íntegra. O harness real foi repetido com as quatro amostras, hashes e banco
inalterados, regressões DAS/DARF/DARE e negativo SEFAZ: `REAL_ISS_GUIDE_VALIDATION=PASS`.

A validação manual estrutural final confirmou os quatro resultados esperados:

- Anápolis retido: `ANAPOLIS_DUAM`, `ISS_WITHHELD`, 1 receita;
- Anápolis próprio: `ANAPOLIS_DUAM`, `ISS_OWN`, 1 receita;
- Nerópolis próprio: `NEROPOLIS_DUAM`, `ISS_OWN`, 1 receita;
- Anápolis atualizado: `ANAPOLIS_DUAM`, `ISS_OWN`, 3 receitas.

O vencimento por receita é uma invariável comprovada do `ANAPOLIS_DUAM`. No
`NEROPOLIS_DUAM`, `due_date` pode permanecer `NULL` quando o documento não expõe o dado
com a mesma granularidade; exigir o campo indistintamente gerava uma asserção de teste
mais forte que o contrato documental real. Saídas finais:
`MANUAL_ISS_PARSER_VALIDATION=PASS` e
`VALIDACAO_MANUAL_CORRIGIDA_S11_1_D=PASS`.

## Fora do escopo preservado

Declaração/automação ISSnet, emissão, consulta de pendências, parcelamentos, NFS-e,
MIT, DCTFWeb, REINF, conciliação, S11.1-E, S11.2, S11.3, S12 e backfill permanecem
fora deste stage. O resultado continua somente em `fiscal_document_parser_runs` quando
um executor autorizado o registrar; esta validação não registrou nada.
