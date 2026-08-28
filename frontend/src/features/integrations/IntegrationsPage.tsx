import { useEffect, useState } from "react";

import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { fetchIntegrationsHealth } from "../../services/lumenService";
import type { IntegrationHealthItem } from "../../types/integration";
import { formatIsoDate, formatStatusLabel } from "../../utils/formatters";

export function IntegrationsPage() {
  const [items, setItems] = useState<IntegrationHealthItem[]>([]);

  useEffect(() => {
    void fetchIntegrationsHealth().then((response) => setItems(response.items));
  }, []);

  return (
    <div className="cards-grid">
      {items.map((item) => (
        <Card key={item.provider}>
          <div className="card-header">
            <h3>{item.label}</h3>
            <Badge tone={item.provider === "ECONTROLE" ? "info" : "muted"}>{formatStatusLabel(item.status)}</Badge>
          </div>
          <div className="detail-grid compact">
            <article>
              <span>Conta</span>
              <strong>{item.account_status ? formatStatusLabel(item.account_status) : "Não configurada"}</strong>
            </article>
            {item.provider === "WATCHER_DOMINIO" ? <>
              <article><span>Última detecção</span><strong>{formatIsoDate(item.watcher_latest_detected_at ?? null)}</strong></article>
              <article><span>Último import</span><strong>{formatIsoDate(item.watcher_latest_import_at ?? null)}</strong></article>
            </> : null}
            <article>
              <span>Ultimo run</span>
              <strong>{item.last_run_status ? formatStatusLabel(item.last_run_status) : "Sem execução"}</strong>
            </article>
            <article>
              <span>Finalizado em</span>
              <strong>{formatIsoDate(item.last_run_at)}</strong>
            </article>
            <article>
              <span>Processados</span>
              <strong>{item.processed_count}</strong>
            </article>
          </div>
          <p className="card-body-copy">{item.note}</p>
        </Card>
      ))}
    </div>
  );
}
