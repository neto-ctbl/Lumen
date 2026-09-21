"""Fail-fast real-corpus validation, SHA-256 and read-only operational DB guards.

Paths are supplied at invocation only. No real paths or fiscal data are logged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from agent.parsers.contracts import DocumentContext, ExtractionStatus, TechnicalFormat
from agent.parsers.runtime import DocumentParserRuntime, default_parser_registry
from agent.parsers.state_guide_pdf import StateGuideFile, StateGuidePdfParser


def _require(condition: object) -> None:
    # Explicit check: python -O/PYTHONOPTIMIZE must not disable real validation.
    if not condition:
        raise AssertionError("DOCUMENT_VALIDATION_CHECK_FAILED")


def file_digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def database_snapshot() -> tuple[object, ...]:
    # Import only in this opt-in harness, never in the parser or ordinary probe.
    from sqlalchemy import create_engine, text
    from backend.app.core.config import Settings

    engine = create_engine(Settings().database_url)
    try:
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            tables = ("fiscal_document_parser_runs", "fiscal_evidences", "watcher_file_events",
                      "fiscal_obligation_statuses", "users")
            counts = tuple(connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() for table in tables)
            revision = tuple(connection.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num")).scalars())
            # Compare row fingerprints too, not only counts. Digests stay local;
            # even a same-count credential/canonical-field mutation is detected.
            fingerprints = tuple(connection.execute(text(
                f"SELECT md5(coalesce(string_agg(row_digest, ',' ORDER BY row_digest), '')) "
                f"FROM (SELECT md5(row_to_json(t)::text) AS row_digest FROM {table} t) s"
            )).scalar_one() for table in tables)
            return counts, revision, fingerprints
    finally:
        engine.dispose()


def _check_file(path: Path, family: str, kind: str | None) -> None:
    original = file_digest(path)
    try:
        context = DocumentContext(file_path=path, technical_format=TechnicalFormat.PDF)
        state_parser = StateGuidePdfParser()
        if family == "UNSUPPORTED":
            _require(state_parser.supports(context) is False)
            _require(state_parser.parse(context).extraction_status is ExtractionStatus.UNSUPPORTED)
            _require(DocumentParserRuntime(default_parser_registry()).run_file(path).extraction_status is ExtractionStatus.UNSUPPORTED)
            return
        result = DocumentParserRuntime(default_parser_registry()).run_file(path)
        _require(result.extraction_status is ExtractionStatus.MATCHED and result.document_family == family)
        if family != "STATE_GUIDE":
            _require(state_parser.supports(context) is False)
            return
        doc, = StateGuideFile.model_validate(result.structured_data).documents
        _require(doc.guide_kind == kind)
        _require(doc.header.layout == "DARE_GO_5_1" and doc.header.uf == "GO")
        _require(all((doc.header.state_registration, doc.header.taxpayer_name, doc.header.reference_label,
                      doc.header.reference_period, doc.header.due_date, doc.header.document_number)))
        _require(doc.header.reference_period.kind != "UNKNOWN")
        _require(doc.header.reference_period_source == "CONTENT_REFERENCE")
        _require(doc.header.total_amount is not None and doc.validation.sum_matches_total is True)
        _require(doc.revenues and all(row.guide_kind == kind and row.components for row in doc.revenues))
    finally:
        _require(file_digest(path) == original)


def run_validation(args: argparse.Namespace) -> int:
    before = None
    failure = None
    try:
        before = database_snapshot()
        _require(before[1] == ("20260911_0019",))
        cases = [
            ("ICMS", args.icms, "STATE_GUIDE", "ICMS"),
            ("DIFAL", args.difal, "STATE_GUIDE", "DIFAL"),
            *[("DIFAL_CONSUMO_ATIVO", path, "STATE_GUIDE", "DIFAL_CONSUMPTION_ASSET")
              for path in args.difal_consumption_asset or [None]],
            ("PROTEGE", args.protege, "STATE_GUIDE", "PROTEGE"),
            ("DAS_REGRESSION", args.das, "DAS", None),
            ("DARF_REGRESSION", args.darf, "DARF", None),
            ("SEFAZ_INSTALLMENT_NEGATIVE", args.sefaz_installment, "UNSUPPORTED", None),
        ]
        for label, path, family, kind in cases:
            if path is None:
                failure = f"{label}_SAMPLE_MISSING"
                break
            try:
                _check_file(path, family, kind)
            except Exception:
                failure = f"{label}_CHECK_FAILED"
                break
            print(f"{label}=PASS")
    except Exception:
        failure = "VALIDATION_SETUP_OR_DATABASE_ERROR"
    finally:
        if before is not None:
            try:
                if database_snapshot() != before:
                    failure = "DATABASE_CHANGED"
            except Exception:
                failure = "DATABASE_FINAL_CHECK_ERROR"
    if failure:
        print(json.dumps({"failure_code": failure}, ensure_ascii=True))
        print("REAL_STATE_GUIDE_VALIDATION=FAIL")
        return 1
    print("REAL_STATE_GUIDE_VALIDATION=PASS")
    return 0


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print("REAL_STATE_GUIDE_VALIDATION=FAIL")
        print('{"failure_code":"VALIDATION_ARGUMENT_ERROR"}')
        raise SystemExit(2)


def main() -> None:
    parser = _SanitizedArgumentParser(description="Read-only, fail-fast state-guide corpus validation.")
    for flag in ("icms", "difal", "protege", "sefaz-installment", "das", "darf"):
        parser.add_argument(f"--{flag}", type=Path)
    parser.add_argument("--difal-consumption-asset", type=Path, action="append")
    raise SystemExit(run_validation(parser.parse_args()))


if __name__ == "__main__":
    main()
