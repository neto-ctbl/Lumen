from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from backend.scripts.fetch_econet_simples_annexes_to_xlsx import (
    _ensure_annex_headers,
    _select_target_rows,
    build_parser,
)


def test_parser_defaults_batch_mode() -> None:
    args = build_parser().parse_args(["--input-xlsx", "a.xlsx"])
    assert args.batch_size == 50
    assert args.query_mode == "missing_only"


def test_select_target_rows_skips_ok_and_prohibited() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Catalogo"
    sheet.append(("CNAE", "anexo_econet_status"))
    sheet.append(("4711-3/02", "OK"))
    sheet.append(("5611-2/01", "PROHIBITED"))
    sheet.append(("6201-5/01", "MISSING_CACHE"))
    sheet.append(("7112-0/00", None))

    header_map = _ensure_annex_headers(sheet)
    rows = _select_target_rows(sheet, header_map=header_map, query_mode="missing_only")
    assert [row.cnae for row in rows] == ["6201501", "7112000"]


def test_select_target_rows_all_keeps_everything() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Catalogo"
    sheet.append(("CNAE Normalizado",))
    sheet.append(("4711302",))
    sheet.append(("5611201",))

    header_map = _ensure_annex_headers(sheet)
    rows = _select_target_rows(sheet, header_map=header_map, query_mode="all")
    assert [row.cnae for row in rows] == ["4711302", "5611201"]
