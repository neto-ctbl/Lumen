export type CompanySummary = {
  id: number;
  cnpj: string;
  razao_social: string;
  nome_fantasia: string | null;
  apelido_pasta: string | null;
  inscricao_estadual: string | null;
  municipio: string | null;
  uf: string | null;
  active: boolean;
  regime_label: string;
};

export type CompanyListResponse = {
  items: CompanySummary[];
};

export type CompanySummaryKpis = {
  obligations_total: number;
  delivered_total: number;
  pending_total: number;
  divergences_total: number;
  evidences_total: number;
  installments_total: number;
};

export type CompanyObligationPreview = {
  obligation_code: string;
  obligation_name: string;
  status: string;
  department: string;
  source: string | null;
  due_date: string | null;
  delivered_at: string | null;
};

export type CompanyDetailResponse = {
  company: CompanySummary;
  period: string;
  cnpj: string;
  inscricao_estadual_display: string;
  municipio_uf: string;
  regime_label: string;
  kpis: CompanySummaryKpis;
  obligations: CompanyObligationPreview[];
  evidences_preview: number;
  divergences_preview: number;
};
