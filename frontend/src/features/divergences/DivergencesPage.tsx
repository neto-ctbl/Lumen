import { useEffect, useState } from "react";

import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { fetchDivergences } from "../../services/lumenService";
import { useLumenUi } from "../../stores/lumenUiStore";
import type { DivergenceItem } from "../../types/fiscal";
import { formatCompanyName, formatDepartmentLabel, formatIsoDate, formatSourceLabel, formatStatusLabel } from "../../utils/formatters";

export function DivergencesPage() {
  const { selectedCompanyId, selectedPeriod } = useLumenUi();
  const [rows, setRows] = useState<DivergenceItem[]>([]);

  useEffect(() => {
    if (!selectedPeriod) {
      setRows([]);
      return;
    }

    void fetchDivergences(selectedPeriod, selectedCompanyId).then((response) => setRows(response.items));
  }, [selectedCompanyId, selectedPeriod]);

  return (
    <div className="cards-grid">
      {rows.length === 0 ? (
        <Card>
          <div className="card-header">
            <h3>Divergências</h3>
          </div>
          <p className="empty-copy">
            Nenhum alerta ou divergencia operacional encontrado para a selecao atual.
          </p>
        </Card>
      ) : (
        rows.map((row) => (
          <Card key={row.id}>
            <div className="card-header">
              <h3>{row.title}</h3>
              <Badge tone={row.severity === "CRITICAL" ? "danger" : "warning"}>{formatStatusLabel(row.severity)}</Badge>
            </div>
            <p className="card-body-copy">{row.message}</p>
            <div className="detail-grid compact">
              <article>
                <span>Empresa</span>
                <strong>{formatCompanyName(row.company_name)}</strong>
              </article>
              <article>
                <span>Departamento</span>
                <strong>{formatDepartmentLabel(row.department)}</strong>
              </article>
              <article>
                <span>Fonte</span>
                <strong>{formatSourceLabel(row.source)}</strong>
              </article>
              <article>
                <span>Criado em</span>
                <strong>{formatIsoDate(row.created_at)}</strong>
              </article>
            </div>
          </Card>
        ))
      )}
    </div>
  );
}
