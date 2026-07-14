import { apiRequest } from "./apiClient";
import type { CompanyDetailResponse, CompanyListResponse } from "../types/company";
import type {
  CockpitResponse,
  DashboardResponse,
  DeliveryListResponse,
  DivergenceListResponse,
  EvidenceListResponse,
  InstallmentListResponse,
  PeriodListResponse,
} from "../types/fiscal";
import type { IntegrationHealthResponse } from "../types/integration";

type QueryValue = string | number | null | undefined;

function buildQuery(params: Record<string, QueryValue>) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

export function fetchCompanies(search = "") {
  return apiRequest<CompanyListResponse>(`/api/v1/lumen/companies${buildQuery({ search })}`);
}

export function fetchPeriods() {
  return apiRequest<PeriodListResponse>("/api/v1/lumen/periods");
}

export function fetchDashboard(period: string) {
  return apiRequest<DashboardResponse>(`/api/v1/lumen/dashboard${buildQuery({ period })}`);
}

export function fetchCockpit(params: {
  period: string;
  companyId?: number | null;
  status?: string | null;
  department?: string | null;
  source?: string | null;
}) {
  return apiRequest<CockpitResponse>(`/api/v1/lumen/cockpit${buildQuery(params)}`);
}

export function fetchCompanySummary(companyId: number, period: string) {
  return apiRequest<CompanyDetailResponse>(
    `/api/v1/lumen/companies/${companyId}/summary${buildQuery({ period })}`,
  );
}

export function fetchDeliveries(period: string, companyId?: number | null) {
  return apiRequest<DeliveryListResponse>(
    `/api/v1/lumen/deliveries${buildQuery({ period, companyId })}`,
  );
}

export function fetchEvidences(period: string, companyId?: number | null) {
  return apiRequest<EvidenceListResponse>(
    `/api/v1/lumen/evidences${buildQuery({ period, companyId })}`,
  );
}

export function fetchDivergences(period: string, companyId?: number | null) {
  return apiRequest<DivergenceListResponse>(
    `/api/v1/lumen/divergences${buildQuery({ period, companyId })}`,
  );
}

export function fetchInstallments(period: string, companyId?: number | null) {
  return apiRequest<InstallmentListResponse>(
    `/api/v1/lumen/installments${buildQuery({ period, companyId })}`,
  );
}

export function fetchIntegrationsHealth() {
  return apiRequest<IntegrationHealthResponse>("/api/v1/lumen/integrations/health");
}
