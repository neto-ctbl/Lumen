from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.fiscal_reference import FiscalReferenceDataset, FiscalReferenceEntry
from backend.app.schemas.fiscal_reference import (
    FiscalReferenceEntryResponse,
    FiscalReferenceSearchResponse,
    FiscalReferenceSourceResponse,
    FiscalReferenceSummaryResponse,
)
from backend.app.services.fiscal_reference import CNAE_LC116, LC116_NBS_IBSCBS, TRIBNAC_NBS_IBSCBS, normalize_cnae, normalize_nbs


def _entry_response(entry: FiscalReferenceEntry) -> FiscalReferenceEntryResponse:
    return FiscalReferenceEntryResponse.model_validate(entry, from_attributes=True)


def _active_entries(db: Session, source_kind: str, column: object, values: set[str]) -> list[FiscalReferenceEntry]:
    if not values:
        return []
    return list(db.scalars(
        select(FiscalReferenceEntry)
        .join(FiscalReferenceDataset, FiscalReferenceEntry.dataset_id == FiscalReferenceDataset.id)
        .where(FiscalReferenceDataset.is_active.is_(True), FiscalReferenceEntry.source_kind == source_kind, column.in_(values))
        .order_by(column, FiscalReferenceEntry.source_row_number)
    ))


def _sources(db: Session) -> list[FiscalReferenceSourceResponse]:
    datasets = db.scalars(
        select(FiscalReferenceDataset).where(FiscalReferenceDataset.is_active.is_(True)).order_by(FiscalReferenceDataset.source_kind)
    )
    return [FiscalReferenceSourceResponse(
        source_kind=item.source_kind, source_title=item.source_title, source_version=item.source_version,
        source_file_name=item.source_file_name, file_sha256=item.file_sha256, imported_at=item.imported_at.isoformat(),
    ) for item in datasets]


def search_fiscal_reference(db: Session, *, search_type: str, query: str) -> FiscalReferenceSearchResponse:
    if search_type == "cnae":
        normalized, _ = normalize_cnae(query)
        if normalized is None:
            raise ValueError("Invalid CNAE. Use seven digits, with or without the official mask.")
        cnae_lc116 = _active_entries(db, CNAE_LC116, FiscalReferenceEntry.cnae, {normalized})
        items = {entry.lc116_item for entry in cnae_lc116 if entry.lc116_item}
        lc116_nbs = _active_entries(db, LC116_NBS_IBSCBS, FiscalReferenceEntry.lc116_item, items)
        nbs_codes = {entry.nbs for entry in lc116_nbs if entry.nbs}
    elif search_type == "nbs":
        normalized, _ = normalize_nbs(query)
        if normalized is None:
            raise ValueError("Invalid NBS. Use digits, with or without the official mask.")
        lc116_nbs = _active_entries(db, LC116_NBS_IBSCBS, FiscalReferenceEntry.nbs, {normalized})
        items = {entry.lc116_item for entry in lc116_nbs if entry.lc116_item}
        cnae_lc116 = _active_entries(db, CNAE_LC116, FiscalReferenceEntry.lc116_item, items)
        nbs_codes = {normalized}
    else:
        raise ValueError("Search type must be 'cnae' or 'nbs'.")
    tribnac_nbs = _active_entries(db, TRIBNAC_NBS_IBSCBS, FiscalReferenceEntry.nbs, nbs_codes)
    return FiscalReferenceSearchResponse(
        search_type=search_type, query=query, normalized_query=normalized,
        summary=FiscalReferenceSummaryResponse(
            cnaes=len({entry.cnae for entry in cnae_lc116 if entry.cnae}),
            lc116_items=len(items), nbs_codes=len(nbs_codes),
            reference_rows=len(cnae_lc116) + len(lc116_nbs) + len(tribnac_nbs),
        ),
        cnae_lc116=[_entry_response(entry) for entry in cnae_lc116],
        lc116_nbs=[_entry_response(entry) for entry in lc116_nbs],
        tribnac_nbs=[_entry_response(entry) for entry in tribnac_nbs],
        sources=_sources(db),
    )
