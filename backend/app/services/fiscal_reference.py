from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.models.fiscal_reference import FiscalReferenceDataset, FiscalReferenceEntry


PARSER_VERSION = "fiscal-reference-v2"
CNAE_LC116 = "CNAE_LC116"
LC116_NBS_IBSCBS = "LC116_NBS_IBSCBS"
TRIBNAC_NBS_IBSCBS = "TRIBNAC_NBS_IBSCBS"
INDOP_RULE = "INDOP_RULE"


@dataclass(frozen=True)
class ParsedWorkbook:
    source_kind: str
    source_title: str
    source_version: str | None
    path: Path
    entries: list[dict[str, Any]]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ImportResult:
    source_kind: str
    status: str
    file_name: str
    file_sha256: str
    rows_imported: int
    physical_rows: int
    rows_skipped: int
    warnings: int
    dataset_id: int | None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _digits(value: Any) -> str | None:
    text = _text(value)
    return re.sub(r"\D", "", text) if text else None


def normalize_cnae(value: Any) -> tuple[str | None, str | None]:
    digits = _digits(value)
    if not digits or len(digits) != 7:
        return None, None
    return digits, f"{digits[:4]}-{digits[4]}/{digits[5:]}"


def normalize_nbs(value: Any) -> tuple[str | None, str | None]:
    digits = _digits(value)
    if not digits:
        return None, None
    formatted = f"{digits[0]}.{digits[1:5]}.{digits[5:7]}.{digits[7:]}" if len(digits) == 9 else _text(value)
    return digits, formatted


def normalize_lc116(value: Any, description: Any = None) -> tuple[str | None, str | None]:
    source = _text(description) or _text(value)
    match = re.match(r"\s*(\d{1,2})\.(\d{1,2})\b", source or "")
    if match:
        major, minor = match.groups()
        return f"{int(major):02d}{int(minor):02d}", f"{int(major)}.{int(minor):02d}"
    digits = _digits(value)
    if not digits:
        return None, None
    digits = digits.zfill(4)
    if len(digits) != 4:
        return None, None
    return digits, f"{int(digits[:2])}.{digits[2:]}"


def normalize_boolean(value: Any) -> bool | None:
    normalized = (_text(value) or "").upper().replace("Ã", "A")
    if normalized in {"S", "SIM", "Y", "YES", "TRUE"}:
        return True
    if normalized in {"N", "NAO", "NO", "FALSE"}:
        return False
    return None


def normalize_code(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return text


def normalize_decimal(value: Any) -> Decimal | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return Decimal(text.replace(",", "."))
    except InvalidOperation:
        return None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _payload(headers: list[str], row: tuple[Any, ...]) -> dict[str, Any]:
    return {header: _text(value) for header, value in zip(headers, row) if header}


def _entry(*, source_kind: str, source_sheet: str, row_number: int, raw_payload: dict[str, Any], **values: Any) -> dict[str, Any]:
    return {"source_kind": source_kind, "source_sheet": source_sheet, "source_row_number": row_number, "raw_payload": raw_payload, **values}


def _worksheet_rows(path: Path, sheet_name: str) -> tuple[list[str], Iterable[tuple[int, tuple[Any, ...]]]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook[sheet_name]
    headers = [_text(value) or "" for value in next(worksheet.iter_rows(min_row=1, max_row=1, values_only=True))]
    def data_rows() -> Iterable[tuple[int, tuple[Any, ...]]]:
        empty_streak = 0
        for row_number, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
            if any(value is not None for value in row):
                empty_streak = 0
                yield row_number, row
            else:
                # Some official workbooks retain Excel's maximum row dimension.
                # No table in this catalog uses intentional 100-row blank gaps.
                empty_streak += 1
                if empty_streak >= 100:
                    break

    return headers, data_rows()


def _merged_effective_values(worksheet) -> dict[tuple[int, int], Any]:
    """Map every merged coordinate to the value of its top-left anchor."""
    values: dict[tuple[int, int], Any] = {}
    for cell_range in worksheet.merged_cells.ranges:
        anchor_value = worksheet.cell(cell_range.min_row, cell_range.min_col).value
        for row_number in range(cell_range.min_row, cell_range.max_row + 1):
            for column_number in range(cell_range.min_col, cell_range.max_col + 1):
                values[(row_number, column_number)] = anchor_value
    return values


def parse_cnae_lc116(path: Path) -> ParsedWorkbook:
    headers, rows = _worksheet_rows(path, "Planilha1")
    entries: list[dict[str, Any]] = []
    warnings = 0
    physical_rows = 0
    for row_number, row in rows:
        physical_rows += 1
        if not any(value is not None for value in row[:8]):
            continue
        # The numeric CNAE column loses a leading zero in Excel; its masked
        # counterpart is authoritative whenever present.
        cnae, cnae_formatted = normalize_cnae(row[0] if len(row) > 0 else row[1])
        item, item_formatted = normalize_lc116(row[3] if len(row) > 3 else None, row[4] if len(row) > 4 else None)
        if cnae is None or item is None:
            warnings += 1
            continue
        entries.append(_entry(
            source_kind=CNAE_LC116, source_sheet="Planilha1", row_number=row_number, raw_payload=_payload(headers, row),
            cnae=cnae, cnae_formatted=cnae_formatted, cnae_description=_text(row[2]), lc116_item=item,
            lc116_item_formatted=item_formatted, lc116_description=_text(row[4]), iss_rate=normalize_decimal(row[5]),
            allows_tax_outside=normalize_boolean(row[6]), lc116_inciso=_text(row[7]),
        ))
    return ParsedWorkbook(CNAE_LC116, "Tabela CNAE x Item LC 116", None, path, entries, {"sheets": ["Planilha1"], "physical_rows": physical_rows, "skipped_rows": warnings, "warnings": warnings, "header_mapping": headers})


def parse_lc116_nbs(path: Path) -> ParsedWorkbook:
    # Read normally to distinguish true merges from ordinary blank cells.
    workbook = load_workbook(path, read_only=False, data_only=True)
    worksheet = workbook["tabela geral"]
    headers = [_text(cell.value) or "" for cell in worksheet[1]]
    merged_values = _merged_effective_values(worksheet)
    entries: list[dict[str, Any]] = []
    warnings = 0
    physical_rows = 0
    for row_number, cells in enumerate(worksheet.iter_rows(min_row=2, values_only=False), start=2):
        row = tuple(cell.value for cell in cells)
        physical_rows += 1
        values = [merged_values.get((row_number, column_number), value) for column_number, value in enumerate(row, start=1)]
        if not any(value is not None for value in values[:10]):
            continue
        item, item_formatted = normalize_lc116(values[0])
        nbs, nbs_formatted = normalize_nbs(values[2])
        if item is None and nbs is None:
            warnings += 1
            continue
        entries.append(_entry(
            source_kind=LC116_NBS_IBSCBS, source_sheet="tabela geral", row_number=row_number, raw_payload=_payload(headers, row),
            lc116_item=item, lc116_item_formatted=item_formatted, lc116_description=_text(values[1]), nbs=nbs,
            nbs_formatted=nbs_formatted, nbs_description=_text(values[3]), onerous=normalize_boolean(values[4]),
            foreign_acquisition=normalize_boolean(values[5]), indop_code=normalize_code(values[6]),
            ibs_incidence_location=_text(values[7]), class_trib_code=normalize_code(values[8]),
            class_trib_description=_text(values[9]),
        ))
    rule_worksheet = workbook["REGRA inc. X"]
    rule_headers = [_text(cell.value) or "" for cell in rule_worksheet[1]]
    for row_number, cells in enumerate(rule_worksheet.iter_rows(min_row=2, values_only=False), start=2):
        row = tuple(cell.value for cell in cells)
        physical_rows += 1
        if not any(value is not None for value in row):
            continue
        entries.append(_entry(source_kind=INDOP_RULE, source_sheet="REGRA inc. X", row_number=row_number, raw_payload=_payload(rule_headers, row)))
    return ParsedWorkbook(LC116_NBS_IBSCBS, "Anexo VIII - Correlacao Item NBS IndOp cClassTrib IBS/CBS", "V1.00.00", path, entries, {"sheets": ["tabela geral", "REGRA inc. X"], "physical_rows": physical_rows, "skipped_rows": warnings, "warnings": warnings, "header_mapping": {"tabela geral": headers, "REGRA inc. X": rule_headers}})


def parse_tribnac_nbs(path: Path) -> ParsedWorkbook:
    headers, rows = _worksheet_rows(path, "Planilha1")
    entries: list[dict[str, Any]] = []
    warnings = 0
    physical_rows = 0
    for row_number, row in rows:
        physical_rows += 1
        if not any(value is not None for value in row[:13]):
            continue
        nbs, nbs_formatted = normalize_nbs(row[2])
        if nbs is None:
            warnings += 1
            continue
        entries.append(_entry(
            source_kind=TRIBNAC_NBS_IBSCBS, source_sheet="Planilha1", row_number=row_number, raw_payload=_payload(headers, row),
            trib_nac_code=normalize_code(row[0]), trib_nac_description=_text(row[1]), nbs=nbs, nbs_formatted=nbs_formatted,
            nbs_description=_text(row[3]), class_trib_code=normalize_code(row[4]), class_trib_description=_text(row[5]),
            cst_code=normalize_code(row[6]), cst_description=_text(row[7]), indop_code=normalize_code(row[8]),
            indop_description=_text(row[9]), onerous=normalize_boolean(row[10]), foreign_acquisition=normalize_boolean(row[11]),
            ibs_incidence_location=_text(row[12]),
        ))
    return ParsedWorkbook(TRIBNAC_NBS_IBSCBS, "Correlacao cTribNac NBS cClassTrib IBS/CBS CST IndOp", None, path, entries, {"sheets": ["Planilha1"], "physical_rows": physical_rows, "skipped_rows": warnings, "warnings": warnings, "header_mapping": headers})


PARSERS = {CNAE_LC116: parse_cnae_lc116, LC116_NBS_IBSCBS: parse_lc116_nbs, TRIBNAC_NBS_IBSCBS: parse_tribnac_nbs}


def import_workbook(db: Session, parsed: ParsedWorkbook, *, dry_run: bool = False) -> ImportResult:
    sha256 = file_sha256(parsed.path)
    existing = db.scalar(
        select(FiscalReferenceDataset).where(
            FiscalReferenceDataset.source_kind == parsed.source_kind,
            FiscalReferenceDataset.file_sha256 == sha256,
            FiscalReferenceDataset.parser_version == PARSER_VERSION,
        )
    )
    if existing is not None:
        return ImportResult(parsed.source_kind, "already_imported", parsed.path.name, sha256, existing.rows_imported, int(existing.import_metadata.get("physical_rows", existing.rows_imported)), 0, int(existing.import_metadata.get("warnings", 0)), existing.id)
    metadata = {**parsed.metadata, "parsed_rows": len(parsed.entries), "file_size_bytes": parsed.path.stat().st_size}
    dataset = FiscalReferenceDataset(source_kind=parsed.source_kind, source_title=parsed.source_title, source_version=parsed.source_version, source_file_name=parsed.path.name, file_sha256=sha256, parser_version=PARSER_VERSION, is_active=False, rows_imported=len(parsed.entries), import_metadata=metadata)
    db.add(dataset)
    db.flush()
    db.add_all(FiscalReferenceEntry(dataset_id=dataset.id, **entry) for entry in parsed.entries)
    db.flush()
    db.execute(update(FiscalReferenceDataset).where(FiscalReferenceDataset.source_kind == parsed.source_kind, FiscalReferenceDataset.id != dataset.id).values(is_active=False))
    dataset.is_active = True
    result = ImportResult(parsed.source_kind, "dry_run" if dry_run else "imported", parsed.path.name, sha256, len(parsed.entries), int(parsed.metadata["physical_rows"]), int(parsed.metadata["skipped_rows"]), int(parsed.metadata["warnings"]), dataset.id)
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return result


def import_reference_files(db: Session, paths: dict[str, Path], *, dry_run: bool = False) -> list[ImportResult]:
    if not paths:
        raise ValueError("At least one source file is required.")
    results: list[ImportResult] = []
    for source_kind, path in paths.items():
        if source_kind not in PARSERS:
            raise ValueError(f"Unsupported source kind: {source_kind}")
        if not path.is_file():
            raise ValueError(f"Source file does not exist: {path}")
        try:
            results.append(import_workbook(db, PARSERS[source_kind](path), dry_run=dry_run))
        except Exception:
            db.rollback()
            raise
    return results


def json_result(results: list[ImportResult]) -> str:
    return json.dumps([result.to_dict() for result in results], ensure_ascii=False, default=str)
