import { useEffect, useState } from "react";

import { Card } from "../../components/ui/Card";
import { Table } from "../../components/ui/Table";
import { fetchInstallments } from "../../services/lumenService";
import { useLumenUi } from "../../stores/lumenUiStore";
import type { InstallmentItem } from "../../types/fiscal";
import { formatCompanyName, formatCurrency, formatIsoDate, formatSourceLabel, formatStatusLabel } from "../../utils/formatters";

export function InstallmentsPage() {
  const { selectedCompanyId, selectedPeriod } = useLumenUi();
  const [rows, setRows] = useState<InstallmentItem[]>([]);

  useEffect(() => {
    if (!selectedPeriod) {
      setRows([]);
      return;
    }

    void fetchInstallments(selectedPeriod, selectedCompanyId).then((response) => setRows(response.items));
  }, [selectedCompanyId, selectedPeriod]);

  return (
    <Card>
      <div className="card-header">
        <h3>Parcelamentos</h3>
        <span>Tabela read-only sem parser ou watcher do S6+.</span>
      </div>
      <Table
          columns={[
          { key: "empresa", header: "Empresa", render: (row) => formatCompanyName(row.company_name) },
          { key: "tipo", header: "Tipo", render: (row) => row.tipo },
          { key: "protocolo", header: "Protocolo", render: (row) => row.protocolo ?? "-" },
          { key: "parcela", header: "Parcela", render: (row) => `${row.parcela_atual ?? 0}/${row.quantidade_parcelas ?? 0}` },
          { key: "valor", header: "Valor", render: (row) => formatCurrency(row.valor_parcela) },
          { key: "vencimento", header: "Vencimento", render: (row) => formatIsoDate(row.vencimento) },
          { key: "status", header: "Status", render: (row) => formatStatusLabel(row.status) },
        ]}
        emptyMessage="Nenhum parcelamento encontrado para a competencia atual."
        rows={rows}
      />
    </Card>
  );
}
