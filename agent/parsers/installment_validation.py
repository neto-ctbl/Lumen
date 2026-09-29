"""Fail-fast real-corpus validation with hashes and read-only DB guards."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from agent.parsers.contracts import DocumentContext, ExtractionStatus, TechnicalFormat
from agent.parsers.darf_pdf import DarfPdfParser
from agent.parsers.das_pdf import DasPdfParser
from agent.parsers.installment_pdf import InstallmentFile, InstallmentPdfParser
from agent.parsers.iss_guide import IssGuidePdfParser
from agent.parsers.runtime import DocumentParserRuntime, default_parser_registry
from agent.parsers.state_guide_pdf import StateGuidePdfParser


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
                connection.execute(
                    text(
                        f"SELECT md5(coalesce(string_agg(row_digest, ',' ORDER BY row_digest), '')) "
                        f"FROM (SELECT md5(row_to_json(t)::text) AS row_digest FROM {table} t) s"
                    )
                ).scalar_one()
                for table in tables
            )
            return counts, revision, fingerprints
    finally:
        engine.dispose()


def _check_positive(path: Path, program: str, layout: str) -> None:
    original = file_digest(path)
    try:
        context = DocumentContext(file_path=path, technical_format=TechnicalFormat.PDF)
        installment_parser = InstallmentPdfParser()
        _require(installment_parser.supports(context) is True)
        for parser in (DasPdfParser(), DarfPdfParser(), StateGuidePdfParser(), IssGuidePdfParser()):
            _require(parser.supports(context) is False)
        result = DocumentParserRuntime(default_parser_registry()).run_file(path)
        _require(result.parser_name == "lumen.installment-pdf")
        _require(result.parser_version == "1")
        _require(result.extraction_status is ExtractionStatus.MATCHED)
        _require(result.document_family == "INSTALLMENT")
        documents = InstallmentFile.model_validate(result.structured_data).documents
        _require(bool(documents))
        _require(all(document.program.value == program for document in documents))
        _require(all(document.header.layout == layout for document in documents))
        _require(all(document.components for document in documents))
        _require(all(document.installment.reference_period for document in documents))
        _require(all(document.payment.due_date for document in documents))
        _require(all(document.payment.total_amount is not None for document in documents))
        _require(all(document.validation.sum_matches_total is True for document in documents))
    finally:
        _require(file_digest(path) == original)


def _check_negative(path: Path, expected_family: str) -> None:
    original = file_digest(path)
    try:
        context = DocumentContext(file_path=path, technical_format=TechnicalFormat.PDF)
        _require(InstallmentPdfParser().supports(context) is False)
        result = DocumentParserRuntime(default_parser_registry()).run_file(path)
        _require(result.extraction_status is ExtractionStatus.MATCHED)
        _require(result.document_family == expected_family)
    finally:
        _require(file_digest(path) == original)


def run_validation(args: argparse.Namespace) -> int:
    before = None
    failure = None
    try:
        before = database_snapshot()
        _require(bool(before[1]))
        positives = (
            ("PGFN_FEDERAL", args.pgfn, "PGFN", "FEDERAL_REVENUE_FORM"),
            ("PGFN_DAS_LIKE", args.pgfn_das_like, "PGFN", "FEDERAL_REVENUE_FORM"),
            ("PARCSN", args.parcsn, "PARCSN", "DAS_FORM"),
            ("PARCMEI", args.parcmei, "PARCMEI", "DAS_FORM"),
            ("RELP", args.relp, "RELP", "DAS_FORM"),
            ("PERT", args.pert, "PERT", "DAS_FORM"),
            ("SIMPLIFICADO", args.simplificado, "SIMPLIFICADO", "DARF_LEGACY_FORM"),
            ("SEFAZ", args.sefaz, "SEFAZ", "DARE_GO_5_1"),
        )
        negatives = (
            ("DAS_REGRESSION", args.das, "DAS"),
            ("DARF_REGRESSION", args.darf, "DARF"),
            ("DARE_REGRESSION", args.dare, "STATE_GUIDE"),
            ("DIFAL_REGRESSION", args.difal, "STATE_GUIDE"),
            ("PROTEGE_REGRESSION", args.protege, "STATE_GUIDE"),
            ("ISS_OWN_REGRESSION", args.iss_own, "ISS_GUIDE"),
            ("ISS_WITHHELD_REGRESSION", args.iss_withheld, "ISS_GUIDE"),
        )
        for label, path, program, layout in positives:
            if path is None:
                raise AssertionError(f"{label}_SAMPLE_MISSING")
            _check_positive(path, program, layout)
            print(f"{label}=PASS")
        for label, path, family in negatives:
            if path is None:
                raise AssertionError(f"{label}_SAMPLE_MISSING")
            _check_negative(path, family)
            print(f"{label}=PASS")
    except Exception as exc:
        failure = str(exc) if str(exc).endswith(("_MISSING", "_CHECK_FAILED")) else "VALIDATION_CHECK_FAILED"
    finally:
        if before is not None:
            try:
                if database_snapshot() != before:
                    failure = "DATABASE_CHANGED"
            except Exception:
                failure = "DATABASE_FINAL_CHECK_ERROR"
    if failure:
        print(json.dumps({"failure_code": failure}, ensure_ascii=True))
        print("REAL_INSTALLMENT_VALIDATION=FAIL")
        return 1
    print("REAL_INSTALLMENT_VALIDATION=PASS")
    return 0


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        print("REAL_INSTALLMENT_VALIDATION=FAIL")
        print('{"failure_code":"VALIDATION_ARGUMENT_ERROR"}')
        raise SystemExit(2)


def main() -> None:
    parser = _SanitizedArgumentParser(description="Read-only S11.1-E real-corpus validation.")
    for flag in (
        "pgfn",
        "pgfn-das-like",
        "parcsn",
        "parcmei",
        "relp",
        "pert",
        "simplificado",
        "sefaz",
        "das",
        "darf",
        "dare",
        "difal",
        "protege",
        "iss-own",
        "iss-withheld",
    ):
        parser.add_argument(f"--{flag}", type=Path)
    raise SystemExit(run_validation(parser.parse_args()))


if __name__ == "__main__":
    main()
