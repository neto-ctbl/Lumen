import { useEffect, useState } from "react";

import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { Table } from "../../components/ui/Table";
import { fetchCockpit } from "../../services/lumenService";
import { useLumenUi } from "../../stores/lumenUiStore";
import type { CockpitCompanyRow } from "../../types/fiscal";
import { formatCnpj, formatCompanyName, formatRegimeLabel, formatStatusLabel } from "../../utils/formatters";

type CockpitPageProps = {
  onOpenCompany: (to: string) => void;
};

export function CockpitPage({ onOpenCompany }: CockpitPageProps) {
  const { filters, selectedCompanyId, selectedPeriod, setFilters } = useLumenUi();
  const [rows, setRows] = useState<CockpitCompanyRow[]>([]);

  useEffect(() => {
    if (!selectedPeriod) {
      setRows([]);
      return;
    }

    void fetchCockpit({
      period: selectedPeriod,
      companyId: selectedCompanyId,
      status: filters.status,
      department: filters.department,
      source: filters.source,
    }).then((response) => setRows(response.items));
  }, [filters.department, filters.source, filters.status, selectedCompanyId, selectedPeriod]);

  return (
    <div className="page-grid">
      <Card className="filters-card">
        <div className="card-header">
          <h3>Filtros do cockpit</h3>
          <span>Período, status, departamento e fonte</span>
        </div>
        <div className="filters-grid">
          <label>
            Status
            <select value={filters.status} onChange={(event) => setFilters({ status: event.target.value })}>
              <option value="">Todos</option>
              <option value="SEM_DADOS">Sem dados</option>
              <option value="PENDENTE">Pendente</option>
              <option value="ENTREGUE">Entregue</option>
              <option value="DIVERGENCIA">Divergência</option>
            </select>
          </label>
          <label>
            Departamento
            <select value={filters.department} onChange={(event) => setFilters({ department: event.target.value })}>
              <option value="">Todos</option>
              <option value="FISCAL">Fiscal</option>
              <option value="DP">DP</option>
              <option value="COMPARTILHADO">Compartilhado</option>
            </select>
          </label>
          <label>
            Fonte
            <select value={filters.source} onChange={(event) => setFilters({ source: event.target.value })}>
              <option value="">Todas</option>
              <option value="MANUAL">Manual</option>
              <option value="ECONTROLE">eControle</option>
            </select>
          </label>
        </div>
      </Card>

      <Card>
        <div className="card-header">
          <h3>Empresas da competencia</h3>
          <span>Clique para abrir a empresa</span>
        </div>
        <Table
          columns={[
            {
              key: "empresa",
              header: "Empresa",
              render: (row) => (
                <button
                  className="inline-link"
                  onClick={() => onOpenCompany(`/lumen/empresa/${row.company_id}?companyId=${row.company_id}&period=${selectedPeriod}`)}
                  type="button"
                >
                  {formatCompanyName(row.razao_social)}
                </button>
              ),
            },
            { key: "cnpj", header: "CNPJ", render: (row) => formatCnpj(row.cnpj) },
            { key: "ie", header: "IE", render: (row) => row.inscricao_estadual_display },
            { key: "regime", header: "Regime", render: (row) => formatRegimeLabel(row.regime_label) },
            {
              key: "status",
              header: "Status",
              render: (row) => <Badge tone={statusTone(row.overall_status)}>{formatStatusLabel(row.overall_status)}</Badge>,
            },
            { key: "obrigacoes", header: "Obrigações", render: (row) => row.obligations_total },
            { key: "pendentes", header: "Pendentes", render: (row) => row.pending_total },
          ]}
          emptyMessage="Nenhuma empresa encontrada para os filtros atuais."
          rows={rows}
        />
      </Card>
    </div>
  );
}

function statusTone(status: string) {
  if (status === "ENTREGUE") return "success";
  if (status === "DIVERGENCIA") return "danger";
  if (status === "PENDENTE") return "warning";
  return "muted";
}
