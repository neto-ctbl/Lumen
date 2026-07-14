import { useEffect, useState } from "react";

import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Table } from "../../components/ui/Table";
import { fetchDeliveries } from "../../services/lumenService";
import { useLumenUi } from "../../stores/lumenUiStore";
import type { DeliveryItem } from "../../types/fiscal";
import { formatCnpj, formatCompanyName, formatDepartmentLabel, formatIsoDate, formatSourceLabel, formatStatusLabel } from "../../utils/formatters";

export function DeliveriesPage() {
  const { selectedCompanyId, selectedPeriod } = useLumenUi();
  const [mode, setMode] = useState<"empresa" | "todas">("empresa");
  const [rows, setRows] = useState<DeliveryItem[]>([]);

  useEffect(() => {
    if (!selectedPeriod) {
      setRows([]);
      return;
    }

    void fetchDeliveries(selectedPeriod, mode === "empresa" ? selectedCompanyId : null).then((response) =>
      setRows(response.items),
    );
  }, [mode, selectedCompanyId, selectedPeriod]);

  return (
    <div className="page-grid">
      <Card>
        <div className="card-header">
          <h3>Modo de leitura</h3>
          <span>Empresa ou todas as empresas</span>
        </div>
        <div className="mode-switch">
          <Button onClick={() => setMode("empresa")} variant={mode === "empresa" ? "primary" : "ghost"}>
            Empresa
          </Button>
          <Button onClick={() => setMode("todas")} variant={mode === "todas" ? "primary" : "ghost"}>
            Todas
          </Button>
        </div>
      </Card>

      <Card>
        <div className="card-header">
          <h3>Tabela operacional de envios</h3>
          <span>Somente leitura, sem disparar jobs ou transmissões.</span>
        </div>
        <Table
          columns={[
            { key: "empresa", header: "Empresa", render: (row) => formatCompanyName(row.company_name) },
            { key: "cnpj", header: "CNPJ", render: (row) => formatCnpj(row.cnpj) },
            { key: "obrigacao", header: "Obrigação", render: (row) => `${row.obligation_code} · ${row.obligation_name}` },
            { key: "departamento", header: "Departamento", render: (row) => <Badge tone="department">{formatDepartmentLabel(row.department)}</Badge> },
            { key: "status", header: "Status", render: (row) => <Badge tone={row.status === "ENTREGUE" ? "success" : "warning"}>{formatStatusLabel(row.status)}</Badge> },
            { key: "fonte", header: "Fonte", render: (row) => formatSourceLabel(row.source) },
            { key: "vencimento", header: "Vencimento", render: (row) => formatIsoDate(row.due_date) },
            { key: "entrega", header: "Entrega", render: (row) => formatIsoDate(row.delivered_at) },
          ]}
          emptyMessage="Nenhum envio operacional encontrado para os filtros atuais."
          rows={rows}
        />
      </Card>
    </div>
  );
}
