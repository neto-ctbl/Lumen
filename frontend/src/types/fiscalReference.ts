export type FiscalReferenceEntry = {
  source_kind: string;
  source_sheet: string;
  source_row_number: number;
  cnae: string | null;
  cnae_formatted: string | null;
  cnae_description: string | null;
  lc116_item: string | null;
  lc116_item_formatted: string | null;
  lc116_description: string | null;
  iss_rate: string | null;
  allows_tax_outside: boolean | null;
  lc116_inciso: string | null;
  trib_nac_code: string | null;
  trib_nac_description: string | null;
  nbs: string | null;
  nbs_formatted: string | null;
  nbs_description: string | null;
  class_trib_code: string | null;
  class_trib_description: string | null;
  cst_code: string | null;
  cst_description: string | null;
  indop_code: string | null;
  indop_description: string | null;
  onerous: boolean | null;
  foreign_acquisition: boolean | null;
  ibs_incidence_location: string | null;
};

export type FiscalReferenceSearchResponse = {
  search_type: "cnae" | "nbs";
  query: string;
  normalized_query: string;
  summary: { cnaes: number; lc116_items: number; nbs_codes: number; reference_rows: number };
  cnae_lc116: FiscalReferenceEntry[];
  lc116_nbs: FiscalReferenceEntry[];
  tribnac_nbs: FiscalReferenceEntry[];
  sources: Array<{ source_kind: string; source_title: string; source_version: string | null; source_file_name: string; file_sha256: string; imported_at: string }>;
};
