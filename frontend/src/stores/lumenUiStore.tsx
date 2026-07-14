import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { fetchCompanies, fetchPeriods } from "../services/lumenService";
import type { CompanySummary } from "../types/company";
import type { PeriodItem } from "../types/fiscal";

export type LumenView =
  | "painel"
  | "cockpit"
  | "empresas"
  | "empresa"
  | "envios"
  | "evidencias"
  | "divergencias"
  | "parcelamentos"
  | "integracoes";

export type LumenFilters = {
  status: string;
  department: string;
  source: string;
};

type NavigateOptions = {
  replace?: boolean;
};

type LumenUiContextValue = {
  companies: CompanySummary[];
  currentView: LumenView;
  filters: LumenFilters;
  focusMode: boolean;
  loadingSelectors: boolean;
  pathname: string;
  periods: PeriodItem[];
  selectedCompany: CompanySummary | null;
  selectedCompanyId: number | null;
  selectedPeriod: string;
  setFilters: (next: Partial<LumenFilters>) => void;
  setFocusMode: (next: boolean) => void;
  setSelectedCompanyId: (companyId: number | null) => void;
  setSelectedPeriod: (period: string) => void;
  navigateTo: (to: string, options?: NavigateOptions) => void;
  companySearch: string;
  setCompanySearch: (value: string) => void;
};

type LumenUiProviderProps = PropsWithChildren<{
  navigate: (to: string, options?: NavigateOptions) => void;
  pathname: string;
}>;

const defaultFilters: LumenFilters = {
  status: "",
  department: "",
  source: "",
};

const LumenUiContext = createContext<LumenUiContextValue | null>(null);

function getViewFromPath(pathname: string): LumenView {
  if (pathname.startsWith("/lumen/cockpit")) return "cockpit";
  if (pathname.startsWith("/lumen/empresas")) return "empresas";
  if (pathname.startsWith("/lumen/empresa/")) return "empresa";
  if (pathname.startsWith("/lumen/envios")) return "envios";
  if (pathname.startsWith("/lumen/evidencias")) return "evidencias";
  if (pathname.startsWith("/lumen/divergencias")) return "divergencias";
  if (pathname.startsWith("/lumen/parcelamentos")) return "parcelamentos";
  if (pathname.startsWith("/lumen/integracoes")) return "integracoes";
  return "painel";
}

function readUrlState(pathname: string) {
  const params = new URLSearchParams(window.location.search);
  const companyIdFromPath = pathname.startsWith("/lumen/empresa/")
    ? Number(pathname.split("/").pop() ?? "")
    : null;
  const companyId = companyIdFromPath || Number(params.get("companyId") ?? "") || null;

  return {
    companyId,
    period: params.get("period") ?? "",
    view: getViewFromPath(pathname),
  };
}

export function LumenUiProvider({ children, navigate, pathname }: LumenUiProviderProps) {
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [periods, setPeriods] = useState<PeriodItem[]>([]);
  const [loadingSelectors, setLoadingSelectors] = useState(true);
  const [companySearch, setCompanySearch] = useState("");
  const [focusMode, setFocusMode] = useState(false);
  const [filters, setFiltersState] = useState<LumenFilters>(defaultFilters);
  const [selectedCompanyId, setSelectedCompanyIdState] = useState<number | null>(
    () => readUrlState(pathname).companyId,
  );
  const [selectedPeriod, setSelectedPeriodState] = useState(() => readUrlState(pathname).period);

  useEffect(() => {
    let cancelled = false;

    async function loadSelectors() {
      setLoadingSelectors(true);
      try {
        const [companyResponse, periodResponse] = await Promise.all([
          fetchCompanies(companySearch),
          fetchPeriods(),
        ]);

        if (cancelled) {
          return;
        }

        setCompanies(companyResponse.items);
        setPeriods(periodResponse.items);

        setSelectedCompanyIdState((current) => {
          if (current && companyResponse.items.some((item) => item.id === current)) {
            return current;
          }
          return companyResponse.items[0]?.id ?? null;
        });

        setSelectedPeriodState((current) => current || periodResponse.items[0]?.competencia || "");
      } finally {
        if (!cancelled) {
          setLoadingSelectors(false);
        }
      }
    }

    void loadSelectors();

    return () => {
      cancelled = true;
    };
  }, [companySearch]);

  useEffect(() => {
    const next = readUrlState(pathname);
    if (next.companyId) {
      setSelectedCompanyIdState(next.companyId);
    }
    if (next.period) {
      setSelectedPeriodState(next.period);
    }
  }, [pathname]);

  function syncUrl(nextPath: string, companyId: number | null, period: string, replace = false) {
    const params = new URLSearchParams(window.location.search);
    if (companyId) {
      params.set("companyId", String(companyId));
    } else {
      params.delete("companyId");
    }

    if (period) {
      params.set("period", period);
    } else {
      params.delete("period");
    }

    const query = params.toString();
    navigate(query ? `${nextPath}?${query}` : nextPath, { replace });
  }

  function setSelectedCompanyId(companyId: number | null) {
    setSelectedCompanyIdState(companyId);
    syncUrl(pathname, companyId, selectedPeriod);
  }

  function setSelectedPeriod(period: string) {
    setSelectedPeriodState(period);
    syncUrl(pathname, selectedCompanyId, period);
  }

  function setFilters(next: Partial<LumenFilters>) {
    setFiltersState((current) => ({ ...current, ...next }));
  }

  const selectedCompany =
    companies.find((company) => company.id === selectedCompanyId) ?? null;

  const value = useMemo<LumenUiContextValue>(
    () => ({
      companies,
      companySearch,
      currentView: getViewFromPath(pathname),
      filters,
      focusMode,
      loadingSelectors,
      navigateTo: (to, options) => navigate(to, options),
      pathname,
      periods,
      selectedCompany,
      selectedCompanyId,
      selectedPeriod,
      setCompanySearch,
      setFilters,
      setFocusMode,
      setSelectedCompanyId,
      setSelectedPeriod,
    }),
    [
      companies,
      companySearch,
      filters,
      focusMode,
      loadingSelectors,
      navigate,
      pathname,
      periods,
      selectedCompany,
      selectedCompanyId,
      selectedPeriod,
    ],
  );

  return <LumenUiContext.Provider value={value}>{children}</LumenUiContext.Provider>;
}

export function useLumenUi() {
  const context = useContext(LumenUiContext);
  if (!context) {
    throw new Error("useLumenUi must be used inside LumenUiProvider.");
  }

  return context;
}
