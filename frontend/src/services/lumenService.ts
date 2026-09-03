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
import type { IntegrationHealthResponse, WatcherHealthResponse } from "../types/integration";
import type {
  DctfwebOriginDetailResponse,
  DctfwebSummaryResponse,
  DominioPayrollCompanyResponse,
  DominioPayrollSummaryResponse,
  FactorRDetailResponse,
  FactorRSummaryResponse,
} from "../types/lumenS9";

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

export function fetchWatcherHealth() {
  return apiRequest<WatcherHealthResponse>("/api/v1/lumen/integrations/watcher-health");
}

export function fetchDominioPayrollSummary(sourcePeriod: string) {
  return apiRequest<DominioPayrollSummaryResponse>(`/api/v1/lumen/dominio/payroll/summary${buildQuery({ sourcePeriod })}`);
}

export function fetchDctfwebSummary(period: string) {
  return apiRequest<DctfwebSummaryResponse>(`/api/v1/lumen/dctfweb/summary${buildQuery({ period })}`);
}

export function fetchFactorRSummary(period: string) {
  return apiRequest<FactorRSummaryResponse>(`/api/v1/lumen/factor-r/summary${buildQuery({ period })}`);
}

export function fetchCompanyDominioPayroll(companyId: number, sourcePeriod: string) {
  return apiRequest<DominioPayrollCompanyResponse>(
    `/api/v1/lumen/companies/${companyId}/dominio/payroll${buildQuery({ sourcePeriod })}`,
  );
}

export function fetchCompanyDctfwebOrigin(companyId: number, period: string) {
  return apiRequest<DctfwebOriginDetailResponse>(
    `/api/v1/lumen/companies/${companyId}/dctfweb-origin${buildQuery({ period })}`,
  );
}

export function fetchCompanyFactorR(companyId: number, period: string) {
  return apiRequest<FactorRDetailResponse>(
    `/api/v1/lumen/companies/${companyId}/factor-r${buildQuery({ period })}`,
  );
}
