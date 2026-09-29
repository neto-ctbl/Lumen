# S11.1-E — Parser documental unificado de parcelamentos

Status: implementado e validado em 2026-09-29.

## Contrato

O parser `lumen.installment-pdf@1` produz uma única família documental,
`INSTALLMENT`, e mantém separadas cinco dimensões:

```text
layout físico
programa de parcelamento
administrador
escopo da dívida
tributos explicitamente identificados
```

O fluxo usa o contrato do S11.1-C.1:

```text
LayoutRegistry -> Extractor -> InstallmentClassifier -> ParserExtraction
```

`DocumentParserRuntime` não foi alterado. O parser foi somente registrado de forma
explícita depois dos parsers de guia normal. A correção não depende dessa ordem:
`DasPdfParser`, `DarfPdfParser`, `StateGuidePdfParser` e `IssGuidePdfParser` continuam
recusando parcelamentos em seus próprios `supports()`.

## Layouts

| Layout | Uso no parcelamento | Decisão |
|---|---|---|
| `DAS_FORM` | PARCSN, PARCMEI, RELP, PERT e variantes PGFN DAS-like | extractor DAS compartilhado após adaptação mínima |
| `FEDERAL_REVENUE_FORM` | PGFN/SISPAR federal | `FederalRevenueGuideExtractor` reutilizado |
| `DARE_GO_5_1` | parcelamento SEFAZ Goiás | `StateRevenueGuideExtractor` reutilizado |
| `DARF_LEGACY_FORM` | Parcelamento Simplificado no DARF clássico numerado | novo layout estrutural comprovado pelo corpus |

Os layouts municipais `ANAPOLIS_DUAM` e `NEROPOLIS_DUAM` permanecem fora deste
parser. Não existe suporte a parcelamento municipal neste stage.

O novo `DARF_LEGACY_FORM` não foi criado por causa do nome do programa. A amostra real
possui formulário físico distinto do SENDA atual: campos numerados, duas vias na mesma
página e ausência da tabela moderna de composição. As duas vias idênticas são
deduplicadas pela identidade documental extraída. O código estrutural `1124`, no
contexto desse formulário, identifica o Parcelamento Simplificado; `SIMPLES NACIONAL`
jamais é tratado como substring de `SIMPLIFICADO`.

## Taxonomia

Programas suportados:

- `PGFN`;
- `PARCSN`;
- `PARCMEI` — aceita os marcadores documentais `PARCMEI` e `SIMEI`;
- `RELP`;
- `PERT`;
- `SIMPLIFICADO`;
- `SEFAZ`;
- `UNKNOWN`, quando o documento é inequivocamente um parcelamento, mas não informa
  programa conclusivo.

Administradores atuais: `PGFN`, `RFB`, `SIMPLES_NACIONAL`, `SEFAZ_GO` e `UNKNOWN`.
Escopos atuais: `FEDERAL`, `SIMPLES_NACIONAL`, `SIMEI`, `STATE` e `UNKNOWN`.

Tributos são extraídos somente de denominações/componentes explícitos. Assim, o corpus
DAS-like identifica combinações de IRPJ, CSLL, PIS, COFINS, INSS e ICMS, e o SEFAZ
identifica ICMS. PGFN e Simplificado permanecem com `taxes=[]` nas amostras observadas:
programa federal não autoriza inventar os tributos da dívida.

`raw_debt_description` é um valor mínimo normalizado. A amostra PGFN usa
`DIVIDA_ATIVA`; observações integrais, textos brutos, linha digitável e código de barras
não entram no resultado.

## Modelo tipado

`InstallmentFile.documents[]` contém:

- `header`: layout, página/bloco e identidade rotulada do contribuinte quando presente;
- `program` e `administrator`;
- `installment`: referência, número do acordo/registro, parcela atual/total, período de
  referência e número documental;
- `debt`: escopo, tributos explícitos, períodos originais extraídos dos componentes e
  descrição mínima;
- `payment`: vencimento, validade, principal, multa, juros, correção e total em `Decimal`;
- `components[]`: código, descrição, período, UF/município, tributo e valores;
- `validation`: soma dos componentes e relação entre vencimento/validade.

Campos ausentes permanecem nulos. Período documental, vencimento e validade não são
convertidos entre si. Filename e path não preenchem parcela, programa, tributo ou
período. O runtime continua podendo preservar `period_from_path` como sinal separado.

## Sinais e conflitos

O classifier usa apenas evidência documental allowlisted, incluindo `PGFN-SISPAR`,
`PARCSN`, `PARCMEI`/`SIMEI`, `RELPSN`/`RELP`, `PERTSN`/`PERT`, parcelamento inequívoco
no DARE e o código estrutural do DARF legado. Um rótulo vazio `PARCELA` presente na
estrutura normal não é suficiente.

Com marcador conclusivo:

```text
parser de guia normal -> UNSUPPORTED
InstallmentPdfParser -> MATCHED / INSTALLMENT
```

Sem marcador conclusivo, os mesmos layouts continuam DAS, DARF ou STATE_GUIDE. Um
filename `PGFN`, `PERT` ou `RELP` sem conteúdo correspondente não altera o resultado.
Layout desconhecido, mesmo contendo palavras de parcelamento, permanece
`UNSUPPORTED`; não há heurística por nome.

## Corpus real e limites

Foram auditadas oito amostras reais externas ao Git: duas variantes PGFN e uma para cada
um dos demais programas:

| Programa | Layout comprovado | Resultado |
|---|---|---|
| PGFN/SISPAR federal atual | `FEDERAL_REVENUE_FORM` | validado |
| PGFN com aparência DAS-like | `FEDERAL_REVENUE_FORM` | validado |
| PARCSN | `DAS_FORM` | validado |
| PARCMEI | `DAS_FORM` | validado; escopo da dívida `SIMEI` |
| RELP | `DAS_FORM` | validado |
| PERT | `DAS_FORM` | validado |
| SIMPLIFICADO | `DARF_LEGACY_FORM` | validado |
| SEFAZ | `DARE_GO_5_1` | validado |

O arquivo operacionalmente nomeado como “PARC SIMPLES” foi classificado como PERT pelo
conteúdo. Nenhum dado fiscal, nome, identificador, valor, path ou hash do corpus foi
copiado para o repositório.

Não há amostras adicionais por cada possível grupo de dívida. Essa ausência não bloqueia
os sete programas, mas impede declarar cobertura tributária exaustiva. PGFN não fornece
parcela atual/total na camada documental observada; esses dados não são recuperados do
filename. O Simplificado informa parcela atual, mas não total. Documento sem camada de
texto continua `INCONCLUSIVE`; OCR não faz parte do stage.

## Probe e validação real

Probe local sanitizado:

```powershell
.\.venv\Scripts\python.exe -m agent.parsers.installment_probe -- '<PDF_LOCAL>'
```

Ele retorna somente família/status, layouts, programas, administradores, escopos,
contagens, presença de campos e warnings. Não retorna path nem dados fiscais.

`agent.parsers.installment_validation` é opt-in e fail-fast. Recebe paths explicitamente,
calcula SHA-256 antes/depois, abre a transação do banco como `READ ONLY` e compara
contagens, revisão Alembic e fingerprints de linhas antes/depois. Não cria evidence,
parser run ou estado canônico.

A matriz real aprovou os oito positivos e os controles negativos reais DAS, DARF, DARE
ICMS, DIFAL, PROTEGE, ISS próprio e ISS retido:

```text
PGFN_FEDERAL=PASS
PGFN_DAS_LIKE=PASS
PARCSN=PASS
PARCMEI=PASS
RELP=PASS
PERT=PASS
SIMPLIFICADO=PASS
SEFAZ=PASS
DAS_REGRESSION=PASS
DARF_REGRESSION=PASS
DARE_REGRESSION=PASS
DIFAL_REGRESSION=PASS
PROTEGE_REGRESSION=PASS
ISS_OWN_REGRESSION=PASS
ISS_WITHHELD_REGRESSION=PASS
REAL_INSTALLMENT_VALIDATION=PASS
```

Nenhuma migration, tabela de parcelamentos, endpoint, tela, polling, backfill,
reconciliação, consulta externa ou promoção canônica foi criada. Controle ativo de
parcelamentos, pagamento, saldo, vigência e inadimplência permanecem fora deste stage.

Fechamento automatizado: suíte focada `228 passed, 1 warning`; backend completo
`970 passed, 1 warning`; Ruff aprovado; typecheck e build aprovados (`62` módulos,
build em `5.31s`); Playwright em `lumen_test` com admin sintético `14 passed` em `2.0m`;
`git diff --check` sem erro e somente avisos LF/CRLF. O Alembic operacional confirmou
`20260925_0020 (head)`: a revisão `0020` já existia no worktree como alteração Domínio
preexistente e não relacionada. O S11.1-E não criou nem alterou migration. Nenhum
PDF/XML/ZIP/render entrou no status; os sete renders temporários da auditoria visual foram
removidos após a inspeção.

Na validação operacional repetida pela usuária, as sete guias passaram na matriz manual,
o harness integral aprovou oito positivos e sete controles, os hashes permaneceram
inalterados, a suíte focada marcou `228 passed`, o backend `970 passed`, Ruff/typecheck/
build passaram e o E2E isolado marcou `14 passed`. Depois, a nomenclatura do programa foi
normalizada de `SIMEI` para `PARCMEI`, preservando `SIMEI` como marcador e escopo. O PDF
real, o harness integral e `17` testes do parser passaram; a suíte focada atualizada marcou
`229 passed`. Uma repetição do backend aprovou 970 casos antes de um `WinError 10055`
ambiental em socket do `TestClient` Econet; o único caso afetado passou isolado. Não houve
alteração documental, bancária, migration ou parser run.
