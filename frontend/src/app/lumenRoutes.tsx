import { CockpitPage } from "../features/cockpit/CockpitPage";
import { CompanyPage } from "../features/company/CompanyPage";
import { CompaniesPage } from "../features/companies/CompaniesPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { DeliveriesPage } from "../features/deliveries/DeliveriesPage";
import { DivergencesPage } from "../features/divergences/DivergencesPage";
import { EvidencesPage } from "../features/evidences/EvidencesPage";
import { InstallmentsPage } from "../features/installments/InstallmentsPage";
import { IntegrationsPage } from "../features/integrations/IntegrationsPage";

type LumenRouteRendererProps = {
  pathname: string;
  onNavigate: (to: string) => void;
};

export function getLumenRouteTitle(pathname: string): string {
  if (pathname.startsWith("/lumen/cockpit")) return "Cockpit Fiscal";
  if (pathname.startsWith("/lumen/empresas")) return "Empresas";
  if (pathname.startsWith("/lumen/empresa/")) return "Empresa";
  if (pathname.startsWith("/lumen/envios")) return "Envios";
  if (pathname.startsWith("/lumen/evidencias")) return "Evidências";
  if (pathname.startsWith("/lumen/divergencias")) return "Divergências";
  if (pathname.startsWith("/lumen/parcelamentos")) return "Parcelamentos";
  if (pathname.startsWith("/lumen/integracoes")) return "Integrações";
  return "Painel";
}

export function renderLumenRoute({ pathname, onNavigate }: LumenRouteRendererProps) {
  if (pathname.startsWith("/lumen/cockpit")) {
    return <CockpitPage onOpenCompany={onNavigate} />;
  }

  if (pathname.startsWith("/lumen/empresas")) {
    return <CompaniesPage onOpenCompany={onNavigate} />;
  }

  if (pathname.startsWith("/lumen/empresa/")) {
    const companyId = Number(pathname.split("/").pop() ?? "");
    return <CompanyPage companyId={companyId} onOpenDeliveries={onNavigate} />;
  }

  if (pathname.startsWith("/lumen/envios")) {
    return <DeliveriesPage />;
  }

  if (pathname.startsWith("/lumen/evidencias")) {
    return <EvidencesPage />;
  }

  if (pathname.startsWith("/lumen/divergencias")) {
    return <DivergencesPage />;
  }

  if (pathname.startsWith("/lumen/parcelamentos")) {
    return <InstallmentsPage />;
  }

  if (pathname.startsWith("/lumen/integracoes")) {
    return <IntegrationsPage />;
  }

  return <DashboardPage onOpenCockpit={onNavigate} />;
}
