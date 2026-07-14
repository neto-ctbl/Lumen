import { useEffect, useState } from "react";

import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { fetchEvidences } from "../../services/lumenService";
import { useLumenUi } from "../../stores/lumenUiStore";
import type { EvidenceItem } from "../../types/fiscal";
import { formatCompanyName, formatCompetencia, formatIsoDate, formatSourceLabel, formatStatusLabel } from "../../utils/formatters";

export function EvidencesPage() {
  const { selectedCompanyId, selectedPeriod } = useLumenUi();
  const [rows, setRows] = useState<EvidenceItem[]>([]);

  useEffect(() => {
    if (!selectedPeriod) {
      setRows([]);
      return;
    }

    void fetchEvidences(selectedPeriod, selectedCompanyId).then((response) => setRows(response.items));
  }, [selectedCompanyId, selectedPeriod]);

  return (
    <div className="cards-grid">
      {rows.length === 0 ? (
        <Card>
          <div className="card-header">
            <h3>Evidências</h3>
          </div>
          <p className="empty-copy">
            Nenhuma evidencia fiscal operacional encontrada para a selecao atual.
          </p>
        </Card>
      ) : (
        rows.map((row) => (
          <Card key={row.id}>
            <div className="card-header">
              <h3>{row.file_name ?? "Arquivo sem nome"}</h3>
              <Badge tone="info">{formatStatusLabel(row.status)}</Badge>
            </div>
            <div className="detail-grid compact">
              <article>
                <span>Empresa</span>
                <strong>{formatCompanyName(row.company_name)}</strong>
              </article>
              <article>
                <span>Origem</span>
                <strong>{formatSourceLabel(row.source)}</strong>
              </article>
              <article>
                <span>Competência</span>
                <strong>{row.competencia_detected ? formatCompetencia(row.competencia_detected) : "-"}</strong>
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
