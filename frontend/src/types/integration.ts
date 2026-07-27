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
};

export type IntegrationHealthResponse = {
  items: IntegrationHealthItem[];
};
