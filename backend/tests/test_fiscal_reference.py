from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import func, select

from backend.app.models.fiscal_reference import FiscalReferenceDataset, FiscalReferenceEntry

from backend.app.services.fiscal_reference import (
    CNAE_LC116,
    LC116_NBS_IBSCBS,
    TRIBNAC_NBS_IBSCBS,
    import_reference_files,
    parse_lc116_nbs,
    normalize_boolean,
    normalize_cnae,
    normalize_lc116,
    normalize_nbs,
)


def test_code_normalizers_preserve_business_codes() -> None:
    assert normalize_cnae("6201-5/01") == ("6201501", "6201-5/01")
    assert normalize_nbs("1.1502.10.00") == ("115021000", "1.1502.10.00")
    assert normalize_nbs("115021000") == ("115021000", "1.1502.10.00")
    assert normalize_lc116("101") == ("0101", "1.01")
    assert normalize_lc116("01.01") == ("0101", "1.01")
    assert normalize_lc116(101, "1.01 - Analise") == ("0101", "1.01")


def test_boolean_normalizer_is_tri_state() -> None:
    assert normalize_boolean("S") is True
    assert normalize_boolean("SIM") is True
    assert normalize_boolean("NÃO") is False
    assert normalize_boolean("N") is False
    assert normalize_boolean("") is None
    assert normalize_boolean("desconhecido") is None


def _workbook(path: Path, headers: list[str], rows: list[list[object]], sheet: str = "Planilha1") -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)
    workbook.save(path)


def test_importer_is_idempotent_and_dry_run_does_not_persist(db_session, tmp_path: Path) -> None:
    source = tmp_path / "cnae.xlsx"
    _workbook(source, ["CNAE (Máscara)", "CNAE", "DESCRIÇÃO CNAE", "ITEM", "LISTA DE SERVIÇOS ANEXA À LEI COMPLEMENTAR Nº 116", "ALÍQUOTA", "PERMITE TRIBUTAR FORA ", "INCISO DA LC 116/2003"], [["6201-5/01", 6201501, "Software", 101, "1.01 - Analise", 0.03, "NÃO", "I"]])
    dry = import_reference_files(db_session, {CNAE_LC116: source}, dry_run=True)
    assert dry[0].status == "dry_run"
    assert db_session.scalar(select(func.count()).select_from(FiscalReferenceDataset)) == 0
    assert db_session.scalar(select(func.count()).select_from(FiscalReferenceEntry)) == 0
    imported = import_reference_files(db_session, {CNAE_LC116: source})
    assert imported[0].rows_imported == 1
    duplicate = import_reference_files(db_session, {CNAE_LC116: source})
    assert duplicate[0].status == "already_imported"


def test_lc116_parser_resolves_only_real_merged_cells(tmp_path: Path) -> None:
    source = tmp_path / "lc116.xlsx"
    workbook = Workbook()
    rules = workbook.active
    rules.title = "REGRA inc. X"
    rules.append(["P/S ONEROSA (S/N)", "ADQ EXTERIOR (S/N)"])
    rules.append(["SIM", "NÃO"])
    table = workbook.create_sheet("tabela geral")
    table.append(["Item LC 116", "Descrição Item", "NBS", "DESCRIÇÃO NBS", "PS ONEROSA? (S/N)", "ADQ EXTERIOR? (S/N)", "INDOP", "Local incidência IBS", "cClassTrib", "nome cClassTrib"])
    table.append(["04.01", "Medicina", "1.2301.22.00", "NBS A", None, None, "030101", "Destino", "000001", "Integral"])
    table.append([None, None, None, None, None, None, "030102", None, None, None])
    table.append([None, None, None, None, None, None, "030103", None, None, None])
    table.append([None, None, None, None, None, None, "030104", None, None, None])
    table.append(["04.02", "Laboratorio", "1.2301.93.00", "NBS B", "S", "N", "050101", "Destino B", "200043", "Reducao"])
    table.append([None, None, None, None, None, None, "050101", None, "200043", "Reducao"])
    table.append([None, None, None, None, None, None, "050102", None, None, None])
    table.merge_cells("A2:A5")
    table.merge_cells("B2:B5")
    table.merge_cells("C2:C5")
    table.merge_cells("D2:D5")
    table.merge_cells("E2:E5")
    table.merge_cells("F2:F5")
    table.merge_cells("I2:I6")
    table.merge_cells("J2:J6")
    table.merge_cells("A6:A8")
    table.merge_cells("B6:B8")
    table.merge_cells("C6:C8")
    table.merge_cells("D6:D8")
    table.merge_cells("G6:G8")
    table.merge_cells("I7:I8")
    workbook.save(source)
    parsed = parse_lc116_nbs(source)
    entries = {entry["source_row_number"]: entry for entry in parsed.entries if entry["source_kind"] == LC116_NBS_IBSCBS}

    assert [entries[row]["lc116_item"] for row in range(2, 6)] == ["0401"] * 4
    assert [entries[row]["class_trib_code"] for row in range(2, 7)] == ["000001"] * 5
    assert [entries[row]["onerous"] for row in range(2, 6)] == [None] * 4
    assert entries[6]["onerous"] is True
    assert [entries[row]["foreign_acquisition"] for row in range(2, 6)] == [None] * 4
    assert entries[6]["foreign_acquisition"] is False
    assert [entries[row]["indop_code"] for row in range(2, 6)] == ["030101", "030102", "030103", "030104"]
    assert [entries[row]["lc116_item"] for row in range(6, 9)] == ["0402"] * 3
    assert [entries[row]["class_trib_code"] for row in range(7, 9)] == ["200043"] * 2
    assert [entries[row]["indop_code"] for row in range(6, 9)] == ["050101"] * 3


def test_tribnac_constant_preserves_zero_codes() -> None:
    assert TRIBNAC_NBS_IBSCBS == "TRIBNAC_NBS_IBSCBS"
