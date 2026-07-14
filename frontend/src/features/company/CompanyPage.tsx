import { useEffect, useState } from "react";

import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { KpiCard } from "../../components/ui/KpiCard";
import { Table } from "../../components/ui/Table";
import { fetchCompanySummary } from "../../services/lumenService";
import { useLumenUi } from "../../stores/lumenUiStore";
import type { CompanyDetailResponse } from "../../types/company";
import { formatCnpj, formatCompanyName, formatCompetencia, formatDepartmentLabel, formatIsoDate, formatRegimeLabel, formatSourceLabel, formatStatusLabel } from "../../utils/formatters";

type CompanyPageProps = {
  companyId: number;
  onOpenDeliveries: (to: string) => void;
};

export function CompanyPage({ companyId, onOpenDeliveries }: CompanyPageProps) {
  const { selectedPeriod } = useLumenUi();
  const [data, setData] = useState<CompanyDetailResponse | null>(null);

  useEffect(() => {
    if (!selectedPeriod || !companyId) {
      setData(null);
      return;
    }

    void fetchCompanySummary(companyId, selectedPeriod).then(setData);
  }, [companyId, selectedPeriod]);

  return (
    <div className="page-grid">
      <Card className="company-summary">
        <div className="company-heading">
          <div>
            <span className="eyebrow">Empresa fiscal</span>
            <h3>{formatCompanyName(data?.company.razao_social ?? "Carregando empresa")}</h3>
          </div>
          <Badge tone="muted">{formatRegimeLabel(data?.regime_label)}</Badge>
        </div>
        <div className="detail-grid">
          <article>
            <span>CNPJ</span>
            <strong>{formatCnpj(data?.cnpj)}</strong>
          </article>
          <article>
            <span>IE</span>
            <strong>{data?.inscricao_estadual_display ?? "ISENTO"}</strong>
          </article>
          <article>
            <span>Município / UF</span>
            <strong>{data?.municipio_uf ?? "-"}</strong>
          </article>
          <article>
            <span>Competência</span>
            <strong>{data?.period ? formatCompetencia(data.period) : "-"}</strong>
          </article>
        </div>
      </Card>

      <section className="kpi-grid">
        <KpiCard label="Obrigações" value={data?.kpis.obligations_total ?? 0} />
        <KpiCard label="Entregues" value={data?.kpis.delivered_total ?? 0} />
        <KpiCard label="Evidências" value={data?.kpis.evidences_total ?? 0} />
        <KpiCard label="Divergências" value={data?.kpis.divergences_total ?? 0} />
      </section>

      <section className="split-grid">
        <Card>
          <div className="card-header">
            <h3>Obrigações da empresa</h3>
            <button
              className="inline-link"
              onClick={() => onOpenDeliveries(`/lumen/envios?companyId=${companyId}&period=${selectedPeriod}`)}
              type="button"
            >
              Abrir tela de envios
            </button>
          </div>
          <Table
            columns={[
              { key: "codigo", header: "Codigo", render: (row) => row.obligation_code },
              { key: "nome", header: "Obrigacao", render: (row) => row.obligation_name },
              { key: "status", header: "Status", render: (row) => formatStatusLabel(row.status) },
              { key: "departamento", header: "Departamento", render: (row) => formatDepartmentLabel(row.department) },
              { key: "fonte", header: "Fonte", render: (row) => formatSourceLabel(row.source) },
              { key: "vencimento", header: "Vencimento", render: (row) => formatIsoDate(row.due_date) },
            ]}
            emptyMessage="Ainda nao ha obrigacoes operacionais materializadas para esta empresa."
            rows={data?.obligations ?? []}
          />
        </Card>

        <Card>
          <div className="card-header">
            <h3>Leituras relacionadas</h3>
            <span>Estado vazio e esperado quando ainda nao existem evidencias ou alertas.</span>
          </div>
          <div className="metric-row">
            <span>Evidências</span>
            <strong>{data?.evidences_preview ?? 0}</strong>
          </div>
          <div className="metric-row">
            <span>Divergências</span>
            <strong>{data?.divergences_preview ?? 0}</strong>
          </div>
          <div className="metric-row">
            <span>Parcelamentos</span>
            <strong>{data?.kpis.installments_total ?? 0}</strong>
          </div>
        </Card>
      </section>
    </div>
  );
}
