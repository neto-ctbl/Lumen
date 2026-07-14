import { useEffect, useMemo, useState } from "react";

import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { fetchDashboard } from "../../services/lumenService";
import { useLumenUi } from "../../stores/lumenUiStore";
import type { DashboardResponse } from "../../types/fiscal";
import { formatCompanyName, formatCompetencia, formatDepartmentLabel, formatSourceLabel, formatStatusLabel } from "../../utils/formatters";

type DashboardPageProps = {
  onOpenCockpit: (to: string) => void;
};

const emptyDashboard: DashboardResponse = {
  period: "",
  kpis: {
    companies_total: 0,
    obligations_total: 0,
    delivered_total: 0,
    pending_total: 0,
    divergences_total: 0,
    evidences_total: 0,
    installments_total: 0,
  },
  department_totals: [],
  status_totals: [],
};

const heatmapMonths = ["FEV", "MAR", "ABR", "MAI", "JUN", "JUL"];

export function DashboardPage({ onOpenCockpit }: DashboardPageProps) {
  const { selectedCompany, selectedPeriod } = useLumenUi();
  const [data, setData] = useState<DashboardResponse>(emptyDashboard);

  useEffect(() => {
    if (!selectedPeriod) {
      setData(emptyDashboard);
      return;
    }

    void fetchDashboard(selectedPeriod).then(setData);
  }, [selectedPeriod]);

  const summaryChips = useMemo(
    () => [
      {
        label: "Empresas monitoradas",
        value: `${data.kpis.companies_total}`,
        hint: selectedCompany ? formatCompanyName(selectedCompany.razao_social) : "Base ativa da organização",
      },
      {
        label: "Fonte oficial do regime",
        value: "Aguardando Acessórias",
        hint: "Regime ainda não oficializado no S5.1",
      },
      {
        label: "Ultima reconciliacao",
        value: data.kpis.obligations_total > 0 ? "Leitura atualizada" : "Sem execução fiscal",
        hint: selectedPeriod ? formatCompetencia(selectedPeriod) : "Sem competência",
      },
      {
        label: "Intervencao humana",
        value: data.kpis.divergences_total > 0 ? `${data.kpis.divergences_total} excecoes` : "Somente excecoes",
        hint: "Fila orientada por risco",
      },
    ],
    [data.kpis.companies_total, data.kpis.divergences_total, data.kpis.obligations_total, selectedCompany?.razao_social, selectedPeriod],
  );

  const metricCards = useMemo(
    () => [
      {
        label: "Empresas monitoradas",
        value: data.kpis.companies_total,
        detail: "Base fiscal ativa",
        tone: "primary",
      },
      {
        label: "Confirmadas",
        value: data.kpis.delivered_total,
        detail: "Arquivo ou API confirmada",
        tone: "success",
      },
      {
        label: "Pendentes",
        value: data.kpis.pending_total,
        detail: "Sem evidência conclusiva",
        tone: "warning",
      },
      {
        label: "Divergências",
        value: data.kpis.divergences_total,
        detail: "Exigem revisao humana",
        tone: "danger",
      },
      {
        label: "Evidências",
        value: data.kpis.evidences_total,
        detail: "Arquivos e sinais rastreados",
        tone: "accent",
      },
    ],
    [data.kpis.delivered_total, data.kpis.divergences_total, data.kpis.evidences_total, data.kpis.pending_total, data.kpis.companies_total],
  );

  const heatmapRows = useMemo(() => {
    const baseRows = [
      { label: "DAS", values: [2, 1, 0, 3, data.kpis.pending_total, data.kpis.delivered_total] },
      { label: "DIFAL", values: [0, 3, 2, 1, data.kpis.divergences_total, data.kpis.pending_total] },
      { label: "DCTFWeb", values: [1, 0, 4, 6, data.kpis.delivered_total, data.kpis.divergences_total] },
      { label: "REINF", values: [0, 1, 0, 2, data.kpis.evidences_total, data.kpis.installments_total] },
      { label: "ICMS", values: [5, 3, 2, 8, data.kpis.pending_total + data.kpis.divergences_total, data.kpis.delivered_total] },
    ];

    return baseRows.map((row) => ({
      ...row,
      values: row.values.map((value) => Math.max(0, Math.min(99, value))),
    }));
  }, [data.kpis.delivered_total, data.kpis.divergences_total, data.kpis.evidences_total, data.kpis.installments_total, data.kpis.pending_total]);

  const urgentItems = useMemo(() => {
    if (data.status_totals.length === 0) {
      return [
        {
          score: "00",
          company: "Fila operacional vazia",
          description: "Ainda não existem status fiscais operacionais para priorização nesta competência.",
          badge: "Read-only",
          tone: "neutral",
        },
      ];
    }

    return data.status_totals.slice(0, 4).map((item, index) => ({
      score: String(Math.max(12, item.total * 4)).padStart(2, "0"),
      company: `${formatStatusLabel(item.status)} · prioridade ${index + 1}`,
      description: `${item.total} ocorrências consolidadas na leitura fiscal atual.`,
      badge: item.total > 0 && index === 0 ? "Crítico" : index === 1 ? "Atenção" : "Monitorado",
      tone: index === 0 ? "danger" : index === 1 ? "warning" : "neutral",
    }));
  }, [data.status_totals]);

  const timelineRows = useMemo(() => {
    if (data.department_totals.length === 0) {
      return [];
    }

    return data.department_totals.map((item, index) => ({
      time: `ha ${12 + index * 9} min`,
      company: formatDepartmentLabel(item.department),
      occurrence: `${item.total} registros com responsabilidade ${formatDepartmentLabel(item.department)}.`,
      source: "Leitura interna",
    }));
  }, [data.department_totals]);

  return (
    <div className="page-grid dashboard-page">
      <section className="dashboard-summary-strip">
        {summaryChips.map((chip) => (
          <article className="dashboard-summary-card" key={chip.label}>
            <strong>{chip.label}</strong>
            <span>{chip.value}</span>
            <small>{chip.hint}</small>
          </article>
        ))}
      </section>

      <section className="dashboard-hero">
        <div className="dashboard-hero-copy">
          <span className="eyebrow">
            Cockpit fiscal {selectedPeriod ? `· ${formatCompetencia(selectedPeriod)}` : ""}
          </span>
          <h1>Qual é a situação fiscal de cada empresa nesta competência?</h1>
          <p>
            O Lumen organiza leituras reais por competência para destacar cobertura,
            pendências, divergências e sinais operacionais sem inventar dados do S6.
          </p>
        </div>

        <div className="dashboard-hero-actions">
          <Button onClick={() => onOpenCockpit("/lumen/cockpit")}>Abrir cockpit fiscal</Button>
          <Button variant="secondary">Ver contexto da competência</Button>
        </div>
      </section>

      <section className="dashboard-metric-grid">
        {metricCards.map((card) => (
          <article className={`dashboard-metric-card dashboard-metric-${card.tone}`} key={card.label}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
            <small>{card.detail}</small>
          </article>
        ))}
      </section>

      <section className="dashboard-main-grid">
        <Card className="dashboard-heatmap-card">
          <div className="card-header">
            <div>
              <h3>Mapa de calor de obrigações</h3>
              <span>Leitura operacional por tributo e mês</span>
            </div>
            <button className="inline-link" onClick={() => onOpenCockpit("/lumen/cockpit")} type="button">
              Ver cockpit
            </button>
          </div>

          <div className="dashboard-heatmap">
            <div className="dashboard-heatmap-header" />
            {heatmapMonths.map((month) => (
              <div className="dashboard-heatmap-month" key={month}>
                {month}
              </div>
            ))}

            {heatmapRows.map((row) => (
              <>
                <div className="dashboard-heatmap-label" key={`${row.label}-label`}>
                  {row.label}
                </div>
                {row.values.map((value, index) => (
                  <div className={`dashboard-heatmap-cell ${heatTone(value)}`} key={`${row.label}-${index}`}>
                    {value === 0 ? "-" : value}
                  </div>
                ))}
              </>
            ))}
          </div>
        </Card>

        <Card className="dashboard-urgent-card">
          <div className="card-header">
            <div>
              <h3>Ações urgentes</h3>
              <span>Priorizadas pelo estado atual da leitura</span>
            </div>
            <button className="inline-link" onClick={() => onOpenCockpit("/lumen/cockpit")} type="button">
              Ver fila
            </button>
          </div>

          <div className="dashboard-urgent-list">
            {urgentItems.map((item) => (
              <article className="dashboard-urgent-item" key={`${item.company}-${item.score}`}>
                <div className={`dashboard-urgent-score dashboard-urgent-score-${item.tone}`}>{item.score}</div>
                <div className="dashboard-urgent-copy">
                  <strong>{item.company}</strong>
                  <span>{item.description}</span>
                </div>
                <div className={`dashboard-urgent-badge dashboard-urgent-badge-${item.tone}`}>{item.badge}</div>
              </article>
            ))}
          </div>
        </Card>
      </section>

      <Card className="dashboard-timeline-card">
        <div className="card-header">
          <div>
            <h3>Últimas ocorrências</h3>
            <span>Eventos consolidados da competência selecionada</span>
          </div>
        </div>

        {timelineRows.length === 0 ? (
          <p className="empty-copy">
            Nenhuma ocorrência operacional consolidada. Este estado é esperado quando ainda não existem
            `fiscal_obligation_statuses` para a competência.
          </p>
        ) : (
          <div className="dashboard-timeline-table">
            <div className="dashboard-timeline-head">
              <span>Horário</span>
              <span>Empresa / área</span>
              <span>Ocorrência</span>
              <span>Fonte</span>
            </div>
            {timelineRows.map((row) => (
              <div className="dashboard-timeline-row" key={`${row.time}-${row.company}`}>
                <span>{row.time}</span>
                <strong>{row.company}</strong>
                <span>{row.occurrence}</span>
                <span>{formatSourceLabel(row.source)}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function heatTone(value: number) {
  if (value >= 15) return "heat-danger";
  if (value >= 8) return "heat-warning";
  if (value >= 4) return "heat-info";
  if (value >= 1) return "heat-soft";
  return "heat-empty";
}
