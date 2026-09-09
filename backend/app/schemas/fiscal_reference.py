from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class FiscalReferenceEntryResponse(BaseModel):
    source_kind: str
    source_sheet: str
    source_row_number: int
    cnae: str | None = None
    cnae_formatted: str | None = None
    cnae_description: str | None = None
    lc116_item: str | None = None
    lc116_item_formatted: str | None = None
    lc116_description: str | None = None
    iss_rate: Decimal | None = None
    allows_tax_outside: bool | None = None
    lc116_inciso: str | None = None
    trib_nac_code: str | None = None
    trib_nac_description: str | None = None
    nbs: str | None = None
    nbs_formatted: str | None = None
    nbs_description: str | None = None
    class_trib_code: str | None = None
    class_trib_description: str | None = None
    cst_code: str | None = None
    cst_description: str | None = None
    indop_code: str | None = None
    indop_description: str | None = None
    onerous: bool | None = None
    foreign_acquisition: bool | None = None
    ibs_incidence_location: str | None = None


class FiscalReferenceSourceResponse(BaseModel):
    source_kind: str
    source_title: str
    source_version: str | None = None
    source_file_name: str
    file_sha256: str
    imported_at: str


class FiscalReferenceSummaryResponse(BaseModel):
    cnaes: int
    lc116_items: int
    nbs_codes: int
    reference_rows: int


class FiscalReferenceSearchResponse(BaseModel):
    search_type: str
    query: str
    normalized_query: str
    summary: FiscalReferenceSummaryResponse
    cnae_lc116: list[FiscalReferenceEntryResponse]
    lc116_nbs: list[FiscalReferenceEntryResponse]
    tribnac_nbs: list[FiscalReferenceEntryResponse]
    sources: list[FiscalReferenceSourceResponse]
