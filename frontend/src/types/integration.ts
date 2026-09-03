export type IntegrationHealthItem = {
  provider: string;
  label: string;
  status: string;
  account_status: string | null;
  last_run_status: string | null;
  last_run_at: string | null;
  processed_count: number;
  error_count: number;
  note: string;
  session_status?: string | null;
  session_loaded_at?: string | null;
  session_validated_at?: string | null;
  session_expires_at?: string | null;
  cache_items?: number | null;
  cache_expired_items?: number | null;
  cache_last_refresh?: string | null;
  watcher_latest_detected_at?: string | null;
  watcher_latest_import_at?: string | null;
};

export type IntegrationHealthResponse = {
  items: IntegrationHealthItem[];
};

export type WatcherHealthResponse = {
  status: string;
  reported_status: string | null;
  received_at: string | null;
  last_error_code: string | null;
  started_at?: string | null;
  last_scan_at?: string | null;
  last_successful_send_at?: string | null;
  counters: Record<string, number>;
};
