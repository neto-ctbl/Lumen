import { type ReactNode, useEffect, useState } from "react";

import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { KpiCard } from "../../components/ui/KpiCard";
import { Table } from "../../components/ui/Table";
import {
  fetchCompanyDctfwebOrigin,
  fetchCompanyDominioPayroll,
  fetchCompanyFactorR,
  fetchCompanySummary,
} from "../../services/lumenService";
import { useLumenUi } from "../../stores/lumenUiStore";
import type { CompanyDetailResponse } from "../../types/company";
import type {
  DctfwebOriginDetailResponse,
  DominioPayrollCompanyResponse,
  FactorRDetailResponse,
} from "../../types/lumenS9";
import {
  formatCnpj,
  formatCompanyName,
  formatCompetencia,
  formatDepartmentLabel,
  formatDisplayText,
  formatIsoDate,
  formatRegimeLabel,
  formatSourceLabel,
  formatStatusLabel,
} from "../../utils/formatters";

type CompanyPageProps = {
  companyId: number;
  onOpenDeliveries: (to: string) => void;
};

type DetailState<T> = {
  data: T | null;
  loading: boolean;
};

const initialDetail = <T,>(): DetailState<T> => ({ data: null, loading: true });

function displayConfidence(value: string | null | undefined) {
  if (value === "LOW") return "Baixa confiança";
  if (value === "MEDIUM") return "Confiança média";
  if (value === "HIGH") return "Alta confiança";
  return value ? formatDisplayText(value) : "Não avaliado";
}

function displayReconciliation(value: string | null | undefined) {
  if (value === "THRESHOLD_DIVERGENCE") return "Divergência";
  return value ? formatDisplayText(value) : "Sem dados";
}

function DetailValue({ children, loading }: { children: ReactNode; loading: boolean }) {
  return <strong>{loading ? "Carregando..." : children}</strong>;
}

export function CompanyPage({ companyId, onOpenDeliveries }: CompanyPageProps) {
  const { selectedPeriod } = useLumenUi();
  const [data, setData] = useState<CompanyDetailResponse | null>(null);
  const [dctfweb, setDctfweb] = useState<DetailState<DctfwebOriginDetailResponse>>(initialDetail);
  const [factorR, setFactorR] = useState<DetailState<FactorRDetailResponse>>(initialDetail);
  const [payroll, setPayroll] = useState<DetailState<DominioPayrollCompanyResponse>>(initialDetail);

  useEffect(() => {
    if (!selectedPeriod || !companyId) {
      setData(null);
      return;
    }

    let cancelled = false;
    setData(null);
    setDctfweb(initialDetail());
    setFactorR(initialDetail());
    setPayroll({ data: null, loading: false });

    const loadOptional = <T,>(request: Promise<T>, setState: (state: DetailState<T>) => void) => {
      void request
        .then((response) => {
          if (!cancelled) setState({ data: response, loading: false });
        })
        .catch((error: unknown) => {
          if (!cancelled) {
            setState({ data: null, loading: false });
          }
        });
    };

    void fetchCompanySummary(companyId, selectedPeriod)
      .then((summary) => {
        if (cancelled) return;
        setData(summary);
        if (summary.dominio_source_period) {
          loadOptional(fetchCompanyDominioPayroll(companyId, summary.dominio_source_period), setPayroll);
        }
      })
      .catch(() => {
        if (!cancelled) setData(null);
      });
    loadOptional(fetchCompanyDctfwebOrigin(companyId, selectedPeriod), setDctfweb);
    loadOptional(fetchCompanyFactorR(companyId, selectedPeriod), setFactorR);

    return () => {
      cancelled = true;
    };
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

      <section className="split-grid">
        <Card>
          <div className="card-header"><h2>Origem DCTFWeb</h2><span>Leitura S9.3</span></div>
          <div className="metric-row"><span>Origem esperada</span><DetailValue loading={dctfweb.loading}>{formatDisplayText(dctfweb.data?.expected_origin) || "Não avaliado"}</DetailValue></div>
          <div className="metric-row"><span>Departamento</span><DetailValue loading={dctfweb.loading}>{formatDepartmentLabel(dctfweb.data?.expected_department) || "Não avaliado"}</DetailValue></div>
          <div className="metric-row"><span>Cobertura Domínio</span><DetailValue loading={dctfweb.loading}>{formatDisplayText(dctfweb.data?.dominio_coverage) || "Não avaliado"}</DetailValue></div>
          <div className="metric-row"><span>Sinais relevantes</span><DetailValue loading={dctfweb.loading}>{dctfweb.data ? [dctfweb.data.dp_signal_present && "DP", dctfweb.data.reinf_signal_present && "Reinf", dctfweb.data.mit_signal_present && "MIT"].filter(Boolean).join(", ") || "Nenhum" : "Não avaliado"}</DetailValue></div>
        </Card>
        <Card>
          <div className="card-header"><h2>Fator R</h2><span>Estimativa conservadora</span></div>
          <div className="metric-row"><span>Aplicabilidade</span><DetailValue loading={factorR.loading}>{formatDisplayText(factorR.data?.applicability_status) || "Não aplicável"}</DetailValue></div>
          <div className="metric-row"><span>Reconciliação</span><DetailValue loading={factorR.loading}>{displayReconciliation(factorR.data?.reconciliation_status)}</DetailValue></div>
          <div className="metric-row"><span>Confiança FS12</span><DetailValue loading={factorR.loading}>{displayConfidence(factorR.data?.fs12_confidence)}</DetailValue></div>
          <div className="metric-row"><span>Estimativa operacional</span><DetailValue loading={factorR.loading}>{factorR.data?.factor_r_estimated ?? "Não disponível"}</DetailValue></div>
          <div className="metric-row"><span>Fator Sittax observado</span><DetailValue loading={factorR.loading}>{factorR.data?.factor_r_sittax_observed ?? "Não disponível"}</DetailValue></div>
        </Card>
        <Card>
          <div className="card-header"><h2>Folha Domínio</h2><span>Evidência estruturada</span></div>
          <div className="metric-row"><span>Competência fonte</span><DetailValue loading={payroll.loading}>{payroll.data ? formatCompetencia(payroll.data.source_period) : "Não avaliado"}</DetailValue></div>
          <div className="metric-row"><span>Competência de avaliação</span><DetailValue loading={payroll.loading}>{payroll.data ? formatCompetencia(payroll.data.assessment_period) : "Não avaliado"}</DetailValue></div>
          <div className="metric-row"><span>Cobertura</span><DetailValue loading={payroll.loading}>{formatDisplayText(payroll.data?.coverage_status) || "Não avaliado"}</DetailValue></div>
          <div className="metric-row"><span>Confiança</span><DetailValue loading={payroll.loading}>{displayConfidence(payroll.data?.monetary_summary?.confidence)}</DetailValue></div>
          <div className="metric-row"><span>Sinais principais</span><DetailValue loading={payroll.loading}>{payroll.data?.signals ? [payroll.data.signals.has_employee && "Empregado", payroll.data.signals.has_pro_labore && "Pró-labore", payroll.data.signals.has_autonomous && "Autônomo", payroll.data.signals.has_inss && "INSS", payroll.data.signals.has_fgts && "FGTS"].filter(Boolean).join(", ") || "Nenhum" : "Não avaliado"}</DetailValue></div>
        </Card>
      </section>
    </div>
  );
}
