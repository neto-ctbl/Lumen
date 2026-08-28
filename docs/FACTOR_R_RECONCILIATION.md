# Factor R Reconciliation

## Purpose

S9.4 derives a conservative `fs12_dominio_estimate` from persisted Domínio `rubrics_summary` schema v2 and combines it with observed Sittax `rbt12`. It never represents official FS12, recalculates PGDAS-D, changes DAS, or transmits anything.

## Sources and boundaries

- Domínio monetary summary is structured input only. `gross_total`, `net_total`, and persisted `raw_text` never fill an estimate.
- `employer_cpp_observed` and `fgts_observed` are report-observed amounts, not proof of effective collection.
- Sittax `rbt12` is the only operational denominator. Missing RBT12 leaves numeric Factor R unset.
- Sittax `factor_r_percent` is percentage points and is normalized to a Decimal ratio (`28` becomes `0.28`).
- Observed annexes are sanitized to Roman annex codes. They do not prove which revenue was subject to Factor R.

## Coverage and confidence

For each PA, the payroll window is the preceding twelve source payroll competences. Only a completed canonical Domínio `ACTIVE_COMPANIES` import proves that the monthly report exists. Absence from that existing report is `CONFIRMED_NO_MOVEMENT`, valid historical coverage with observed zero movement; it is not `REPORT_MISSING`. A missing canonical report is `REPORT_MISSING` and is never converted to zero. The current company model has no canonical opening-date history, so the engine does not infer `SHORT_HISTORY`.

`PARTIAL` monetary summaries remain usable when the unclassified amount is proven zero or irrelevant. Unknown or potentially FS12-relevant unclassified rubrics reduce confidence and block strong threshold alerts. Monthly Domínio reports do not prove 13th-salary coverage or cash/recollection basis; those limitations remain reason codes.

## Applicability and alerts

`POTENTIAL` is derived from Simples, non-MEI status and canonical Econet CNAE potential. `EFFECTIVE` requires that same potential plus PA evidence, currently an explicit observed Sittax Factor R; a snapshot never expands the CNAE-derived target universe by itself. A target-company MEI is not confused with a supplier that may itself be an MEI; the current Domínio data cannot determine the specific LC 123 art. 18-B contractor case, so it remains a coverage limitation rather than a generic exclusion.

When a PA lacks canonical Sittax snapshots, the existing S7 read-only-source workflow is `backend/scripts/sync_sittax_apuracoes.py --org-slug <org> --period YYYY-MM`. It uses the observed apuracao read endpoint and persists only the local canonical snapshot; it must be run later with the required authenticated Sittax context, never by the Factor R reconciler.

`resumosTributacaoSittax` is retained as observed payload. It becomes a sanitized annex code only when the payload explicitly provides an annex value that the parser can recognize; the reconciler never infers III or V from descriptive tax-summary fields alone.

The threshold is exactly `Decimal("0.28")`: ratio at or above it maps to III; lower maps to V. Threshold divergence is persisted when observed and estimated sides differ, but its alert requires sufficient component confidence. Near-threshold low-confidence results receive a reason code, not a categorical error conclusion.

## S9.5 operational reading

The Company Page consumes the persisted Factor R detail together with independent DCTFWeb and Domínio detail reads. A `THRESHOLD_DIVERGENCE` is presented as a review-oriented divergence, and `LOW` FS12 confidence is displayed explicitly as low confidence; the interface does not claim that Sittax is wrong. The page does not calculate Factor R, reconstruct RBT12, or infer a payroll competence.

The S9.5 E2E fixture is synthetic and validates an estimated ratio of `0.29`, observed Sittax ratio of `0.27`, threshold divergence, and low confidence. This proves presentation of the persisted assessment without exposing production company data.
