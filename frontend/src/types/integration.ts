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
};

export type IntegrationHealthResponse = {
  items: IntegrationHealthItem[];
};
