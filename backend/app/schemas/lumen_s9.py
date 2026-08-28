from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class DominioPayrollSummaryResponse(BaseModel):
    source_period: str
    assessment_period: str
    canonical_import_present: bool
    selection_scope: str | None = None
    import_status: str | None = None
    companies: int = 0
    matched: int = 0
    unmatched: int = 0
    warnings: int = 0
    schema_v2_movements: int = 0
    monetary_complete: int = 0
    monetary_partial: int = 0
    monetary_insufficient: int = 0
    unclassified_monetary_movements: int = 0


class DominioPayrollSignals(BaseModel):
    has_employee: bool
    has_pro_labore: bool
    has_autonomous: bool
    has_inss: bool
    has_fgts: bool
    has_termination: bool
    has_vacation: bool
    has_leave: bool


class DominioMonetarySummary(BaseModel):
    schema_version: int | None = None
    confidence: str | None = None
    employee_remuneration: str | None = None
    pro_labore: str | None = None
    autonomous: str | None = None
    thirteenth_salary: str | None = None
    employer_cpp_observed: str | None = None
    fgts_observed: str | None = None
    unclassified_monetary_amount: str | None = None


class DominioPayrollCompanyResponse(BaseModel):
    company_id: int
    source_period: str
    assessment_period: str
    coverage_status: str
    match_status: str | None = None
    signals: DominioPayrollSignals | None = None
    monetary_summary: DominioMonetarySummary | None = None
    warning_codes: list[str] = Field(default_factory=list)


class DctfwebOriginItem(BaseModel):
    company_id: int
    expected_origin: str
    expected_department: str | None = None
    dominio_coverage: str
    dp_signal_present: bool
    reinf_signal_present: bool
    mit_signal_present: bool
    fiscal_signal_present: bool
    dctfweb_observed: bool
    classification_confidence: str
    reason_codes: list[str]
    evaluated_at: str


class DctfwebOriginListResponse(BaseModel):
    period: str
    total: int
    items: list[DctfwebOriginItem]


class DctfwebSummaryResponse(BaseModel):
    period: str
    evaluated: int
    dp: int
    fiscal: int
    shared: int
    undetermined: int
    dominio_report_missing: int
    reinf_signal_companies: int
    mit_signal_companies: int
    dctfweb_observed: int


class FactorRItem(BaseModel):
    company_id: int
    applicability_status: str
    calculation_status: str
    fs12_confidence: str
    factor_r_estimated: Decimal | None = None
    factor_r_sittax_observed: Decimal | None = None
    factor_r_delta: Decimal | None = None
    threshold_side: str | None = None
    reconciliation_status: str
    reason_codes: list[str]
    evaluated_at: str


class FactorRListResponse(BaseModel):
    period: str
    total: int
    items: list[FactorRItem]


class FactorRDetailResponse(FactorRItem):
    payroll_window_start: str
    payroll_window_end: str
    payroll_months_expected: int
    payroll_months_covered: int
    payroll_months_with_movement: int
    payroll_months_confirmed_zero: int
    payroll_months_missing: int
    fs12_dominio_estimate: Decimal | None = None
    fs12_breakdown: dict[str, str]
    rbt12_value: Decimal | None = None
    rbt12_source: str | None = None
    rbt12_confidence: str
    estimated_annex: str | None = None
    sittax_observed_annexes: list[str]


class FactorRSummaryResponse(BaseModel):
    period: str
    target_companies: int
    potential: int
    effective: int
    review: int
    not_applicable: int
    full_payroll_coverage: int
    partial_payroll_coverage: int
    fs12_estimated: int
    fs12_high: int
    fs12_medium: int
    fs12_low: int
    fs12_insufficient: int
    rbt12_available: int
    factor_r_calculated: int
    above_or_equal_28: int
    below_28: int
    sittax_factor_observed: int
    threshold_matches: int
    threshold_divergences: int
    near_threshold_low_confidence: int
    annex_reviews: int
    thirteenth_coverage_limitation: int
    unclassified_relevant_limitation: int


class ReconcileRequest(BaseModel):
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    company_id: int | None = None
    dry_run: bool = False


class ReconcileResponse(BaseModel):
    summary: dict[str, int | str | bool]
