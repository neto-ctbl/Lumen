export type PeriodItem = {
  id: number;
  competencia: string;
  year: number;
  month: number;
  status: string;
};

export type PeriodListResponse = {
  items: PeriodItem[];
};

export type DashboardKpis = {
  companies_total: number;
  obligations_total: number;
  delivered_total: number;
  pending_total: number;
  divergences_total: number;
  evidences_total: number;
  installments_total: number;
};

export type DashboardResponse = {
  period: string;
  kpis: DashboardKpis;
  department_totals: Array<{ department: string; total: number }>;
  status_totals: Array<{ status: string; total: number }>;
};

export type CockpitCompanyRow = {
  company_id: number;
  razao_social: string;
  nome_fantasia: string | null;
  cnpj: string;
  inscricao_estadual_display: string;
  regime_label: string;
  department: string | null;
  source: string | null;
  overall_status: string;
  obligations_total: number;
  delivered_total: number;
  pending_total: number;
  divergences_total: number;
};

export type CockpitResponse = {
  period: string;
  items: CockpitCompanyRow[];
};

export type DeliveryItem = {
  obligation_status_id: number;
  company_id: number;
  company_name: string;
  cnpj: string;
  obligation_code: string;
  obligation_name: string;
  status: string;
  department: string;
  source: string | null;
  due_date: string | null;
  delivered_at: string | null;
};

export type DeliveryListResponse = {
  period: string;
  items: DeliveryItem[];
};

export type EvidenceItem = {
  id: number;
  company_id: number | null;
  company_name: string | null;
  source: string;
  source_type: string;
  file_name: string | null;
  detected_tax: string | null;
  detected_obligation: string | null;
  competencia_detected: string | null;
  status: string;
  created_at: string | null;
};

export type EvidenceListResponse = {
  period: string;
  items: EvidenceItem[];
};

export type DivergenceItem = {
  id: number;
  company_id: number | null;
  company_name: string | null;
  code: string;
  title: string;
  message: string;
  severity: string;
  department: string;
  source: string;
  status: string;
  created_at: string | null;
};

export type DivergenceListResponse = {
  period: string;
  items: DivergenceItem[];
};

export type InstallmentItem = {
  id: number;
  company_id: number;
  company_name: string;
  tipo: string;
  protocolo: string | null;
  quantidade_parcelas: number | null;
  parcela_atual: number | null;
  valor_parcela: number | null;
  vencimento: string | null;
  status: string;
  source: string;
  ultima_competencia_detectada: string | null;
};

export type InstallmentListResponse = {
  period: string;
  items: InstallmentItem[];
};
