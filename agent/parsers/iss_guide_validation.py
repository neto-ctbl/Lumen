"""Fail-fast, read-only validation for real ISS guides and regression samples."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from agent.parsers.contracts import DocumentContext, ExtractionStatus, TechnicalFormat
from agent.parsers.iss_guide import IssGuideFile, IssGuidePdfParser
from agent.parsers.runtime import DocumentParserRuntime, default_parser_registry


def _require(condition: object) -> None:
    if not condition:
        raise AssertionError("DOCUMENT_VALIDATION_CHECK_FAILED")


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def database_snapshot() -> tuple[object, ...]:
    from sqlalchemy import create_engine, text

    from backend.app.core.config import Settings

    engine = create_engine(Settings().database_url)
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            tables = (
                "fiscal_document_parser_runs",
                "fiscal_evidences",
                "watcher_file_events",
                "fiscal_obligation_statuses",
                "users",
            )
            counts = tuple(
                connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
                for table in tables
            )
            revision = tuple(
                connection.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num")).scalars()
            )
            fingerprints = tuple(
                connection.execute(text(
                    f"SELECT md5(coalesce(string_agg(row_digest, ',' ORDER BY row_digest), '')) "
                    f"FROM (SELECT md5(row_to_json(t)::text) AS row_digest FROM {table} t) s"
                )).scalar_one()
                for table in tables
            )
            return counts, revision, fingerprints
    finally:
        engine.dispose()


def _check_iss(path: Path, expected: str) -> str:
    before = file_digest(path)
    try:
        result = DocumentParserRuntime(default_parser_registry()).run_file(path)
        _require(result.extraction_status is ExtractionStatus.MATCHED)
        _require(result.document_family == "ISS_GUIDE")
        documents = IssGuideFile.model_validate(result.structured_data).documents
        _require(documents)
        _require(all(document.classification.classification == expected for document in documents))
        _require(all(
            document.header.reference_period
            or all(revenue.reference_period for revenue in document.revenues)
            for document in documents
        ))
        _require(all(document.header.due_date for document in documents))
        _require(all(document.header.document_number for document in documents))
        _require(all(document.header.total_amount is not None for document in documents))
        _require(all(document.validation.sum_matches_total is True for document in documents))
        return documents[0].header.layout
    finally:
        _require(file_digest(path) == before)


def _check_negative(path: Path, expected_family: str | None = None) -> None:
    before = file_digest(path)
    try:
        context = DocumentContext(file_path=path, technical_format=TechnicalFormat.PDF)
        parser = IssGuidePdfParser()
        result = parser.parse(context)
        _require(result.extraction_status is ExtractionStatus.UNSUPPORTED)
        _require(result.document_family == "UNKNOWN")
        if expected_family:
            runtime = DocumentParserRuntime(default_parser_registry()).run_file(path)
            _require(runtime.extraction_status is ExtractionStatus.MATCHED)
            _require(runtime.document_family == expected_family)
    finally:
        _require(file_digest(path) == before)


def run_validation(args: argparse.Namespace) -> int:
    before = None
    failure = None
    try:
        before = database_snapshot()
        _require(before[1] == ("20260911_0019",))
        _require(args.iss_own and args.iss_withheld)
        own_layouts = {_check_iss(path, "ISS_OWN") for path in args.iss_own}
        print("ISS_OWN_REAL=PASS")
        withheld_layouts = {_check_iss(path, "ISS_WITHHELD") for path in args.iss_withheld}
        print("ISS_WITHHELD_REAL=PASS")
        _require(bool(own_layouts & withheld_layouts))
        print("SAME_LAYOUT_OWN_AND_WITHHELD=PASS")
        for path in args.municipal_negative or ():
            _check_negative(path)
        print("MUNICIPAL_NEGATIVES=PASS")
        for path, family, label in (
            (args.das, "DAS", "DAS_REGRESSION"),
            (args.darf, "DARF", "DARF_REGRESSION"),
            (args.state, "STATE_GUIDE", "STATE_GUIDE_REGRESSION"),
        ):
            _require(path is not None)
            _check_negative(path, family)
            print(f"{label}=PASS")
        if args.sefaz_installment is not None:
            _check_negative(args.sefaz_installment)
            print("SEFAZ_INSTALLMENT_NEGATIVE=PASS")
    except Exception:
        failure = "ISS_REAL_VALIDATION_CHECK_FAILED"
    finally:
        if before is not None:
            try:
                if database_snapshot() != before:
                    failure = "DATABASE_CHANGED"
            except Exception:
                failure = "DATABASE_FINAL_CHECK_ERROR"
    if failure:
        print(json.dumps({"failure_code": failure}, ensure_ascii=True))
        print("REAL_ISS_GUIDE_VALIDATION=FAIL")
        return 1
    print("REAL_ISS_GUIDE_VALIDATION=PASS")
    return 0


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        print("REAL_ISS_GUIDE_VALIDATION=FAIL")
        print('{"failure_code":"VALIDATION_ARGUMENT_ERROR"}')
        raise SystemExit(2)


def main() -> None:
    parser = _SanitizedArgumentParser(description="Read-only, fail-fast ISS-guide corpus validation.")
    parser.add_argument("--iss-own", type=Path, action="append")
    parser.add_argument("--iss-withheld", type=Path, action="append")
    parser.add_argument("--municipal-negative", type=Path, action="append")
    parser.add_argument("--das", type=Path)
    parser.add_argument("--darf", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--sefaz-installment", type=Path)
    raise SystemExit(run_validation(parser.parse_args()))


if __name__ == "__main__":
    main()
