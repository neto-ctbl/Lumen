export type DominioPayrollSummaryResponse = {
  source_period: string;
  assessment_period: string;
  canonical_import_present: boolean;
  companies: number;
  matched: number;
  warnings: number;
  schema_v2_movements: number;
  monetary_complete: number;
  monetary_partial: number;
  monetary_insufficient: number;
};

export type DctfwebSummaryResponse = {
  period: string;
  evaluated: number;
  dp: number;
  fiscal: number;
  shared: number;
  undetermined: number;
};

export type FactorRSummaryResponse = {
  period: string;
  target_companies: number;
  effective: number;
  review: number;
  factor_r_calculated: number;
  threshold_divergences: number;
  fs12_low: number;
  fs12_medium: number;
  fs12_high: number;
};

export type DominioPayrollCompanyResponse = {
  company_id: number;
  source_period: string;
  assessment_period: string;
  coverage_status: string;
  match_status: string | null;
  signals: {
    has_employee: boolean;
    has_pro_labore: boolean;
    has_autonomous: boolean;
    has_inss: boolean;
    has_fgts: boolean;
    has_termination: boolean;
    has_vacation: boolean;
    has_leave: boolean;
  } | null;
  monetary_summary: {
    schema_version: number | null;
    confidence: string | null;
  } | null;
  warning_codes: string[];
};

export type DctfwebOriginDetailResponse = {
  company_id: number;
  expected_origin: string;
  expected_department: string | null;
  dominio_coverage: string;
  dp_signal_present: boolean;
  reinf_signal_present: boolean;
  mit_signal_present: boolean;
  fiscal_signal_present: boolean;
  dctfweb_observed: boolean;
  classification_confidence: string;
  reason_codes: string[];
  evaluated_at: string;
};

export type FactorRDetailResponse = {
  company_id: number;
  applicability_status: string;
  calculation_status: string;
  fs12_confidence: string;
  factor_r_estimated: string | number | null;
  factor_r_sittax_observed: string | number | null;
  factor_r_delta: string | number | null;
  reconciliation_status: string;
  payroll_window_start: string;
  payroll_window_end: string;
  payroll_months_covered: number;
  payroll_months_expected: number;
};
