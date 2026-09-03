import { useEffect, useState } from "react";

import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { fetchIntegrationsHealth, fetchWatcherHealth } from "../../services/lumenService";
import type { IntegrationHealthItem, WatcherHealthResponse } from "../../types/integration";
import { formatIsoDate, formatStatusLabel } from "../../utils/formatters";

const watcherStatusLabels: Record<string, string> = {
  NEVER_SEEN: "Não iniciado",
  RUNNING: "Online",
  DEGRADED: "Atenção",
  STOPPED: "Parado",
  STALE: "Offline",
};

export function IntegrationsPage() {
  const [items, setItems] = useState<IntegrationHealthItem[]>([]);
  const [watcher, setWatcher] = useState<WatcherHealthResponse | null>(null);

  useEffect(() => {
    void fetchIntegrationsHealth().then((response) => setItems(response.items));
    void fetchWatcherHealth().then(setWatcher);
  }, []);

  return (
    <div className="cards-grid">
      <Card>
        <div className="card-header">
          <h3>Watcher fiscal</h3>
          <Badge tone={watcher?.status === "RUNNING" ? "info" : "muted"}>{watcherStatusLabels[watcher?.status ?? "NEVER_SEEN"]}</Badge>
        </div>
        <div className="detail-grid compact">
          <article><span>Ultimo heartbeat</span><strong>{formatIsoDate(watcher?.received_at ?? null)}</strong></article>
          <article><span>Ultimo scan</span><strong>{formatIsoDate(watcher?.last_scan_at ?? null)}</strong></article>
          <article><span>Pendentes</span><strong>{watcher?.counters.pending_retry ?? 0}</strong></article>
        </div>
        <p className="card-body-copy">{watcher?.last_error_code ? `Diagnostico: ${watcher.last_error_code}` : "Estado recebido do agent; nao inicia nem envia arquivos."}</p>
      </Card>
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
