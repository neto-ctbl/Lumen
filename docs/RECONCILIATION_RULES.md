# Reconciliation Rules

## DCTFWeb expected origin

The S9.3 reconciliation produces an operational expectation, not a legal conclusion or a delivery confirmation.

- A canonical Domínio `ACTIVE_COMPANIES` import with a matched movement gives `CONFIRMED_MOVEMENT` coverage.
- A canonical import without the company gives `CONFIRMED_NO_MOVEMENT`; it only means no payroll movement was observed.
- Missing canonical import gives `REPORT_MISSING`; it never proves absence of DP.
- Employee, pro-labore, autonomous, INSS, termination, vacation and leave signals may establish a DP component. FGTS alone does not.
- DCTFWeb is treated operationally as the composition of eSocial, EFD-Reinf and MIT components: eSocial maps to DP; REINF and MIT map to Fiscal.
- REINF detection is explicit and accepts only canonical `REINF` status or evidence.
- MIT detection starts only at PA `2025-01` and currently accepts only canonical `PIS` and `COFINS`, because these are the federal MIT-backed obligations represented in the local rules. DAS is not MIT, regime alone is not MIT, and `EFD_CONTRIBUICOES` is not MIT.
- DP plus Fiscal is `COMPARTILHADO`; Fiscal plus confirmed no DP movement is `FISCAL`; Fiscal with missing Domínio coverage is `UNDETERMINED`.
- A canonical DCTFWeb status, evidence or mapped Acessorias delivery observes the obligation but does not determine origin or confirm delivery by itself.
- Every currently active `ExternalCompany.active = true` company is assessed for the organization and period. There is no historical active-state table yet, so S9.3 uses the current active flag as an operational limitation.
- Active companies without DP, REINF, MIT or DCTFWeb signals are persisted as `UNDETERMINED` with `NO_DCTFWEB_COMPONENT_OBSERVED`, no expected department and no actionable alert.
- Missing Domínio coverage is alerted once per organization and period with `company_id = null`, not once per company.

The reconciliation never writes `fiscal_obligation_statuses`. It stores `expected_origin` and `expected_responsible_department` in `dctfweb_origin_assessments` and manages only its operational alerts.

## S9.3 audit snapshot

The 2026-08-21 audit of `2026-07` found no canonical PIS/COFINS status or evidence, so MIT remained zero. It also found no canonical DCTFWeb status, evidence or mapped Acessorias delivery, so DCTFWeb observed remained zero. These are data-state results, not negative legal conclusions.
