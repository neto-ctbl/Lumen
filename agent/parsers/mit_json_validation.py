"""Read-only and sanitized validation for a real MIT JSON sample."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from agent.parsers.contracts import ExtractionStatus
from agent.parsers.mit_json import MIT_JSON_LAYOUT_ID, sanitized_mit_json_probe


def _require(condition: object) -> None:
    if not condition:
        raise AssertionError("MIT_VALIDATION_CHECK_FAILED")


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
            )
            counts = tuple(
                connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
                for table in tables
            )
            revision = tuple(
                connection.execute(
                    text("SELECT version_num FROM alembic_version ORDER BY version_num")
                ).scalars()
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


def run_validation(
    path: Path,
    *,
    expected_debits: int | None = None,
    expected_taxes: frozenset[str] | None = None,
    expected_warnings: frozenset[str] | None = None,
) -> int:
    before_db: tuple[object, ...] | None = None
    before_hash: str | None = None
    failure: str | None = None
    probe = None
    try:
        before_hash = file_digest(path)
        before_db = database_snapshot()
        probe = sanitized_mit_json_probe(path)
        _require(probe.family == "MIT")
        _require(probe.layout_id == MIT_JSON_LAYOUT_ID and probe.layout_known)
        _require(probe.extraction_status is ExtractionStatus.MATCHED and probe.matched)
        _require(probe.has_assessment_period)
        if expected_debits is not None:
            _require(probe.debits_count == expected_debits)
        if expected_taxes is not None:
            _require(frozenset(probe.taxes) == expected_taxes)
        if expected_warnings is not None:
            _require(frozenset(probe.warning_codes) == expected_warnings)
    except Exception as exc:
        failure = (
            str(exc)
            if str(exc).endswith(("_MISSING", "_CHECK_FAILED"))
            else "MIT_VALIDATION_CHECK_FAILED"
        )
    finally:
        try:
            if before_hash is not None and file_digest(path) != before_hash:
                failure = "MIT_SAMPLE_CHANGED"
            if before_db is not None and database_snapshot() != before_db:
                failure = "DATABASE_CHANGED"
        except Exception:
            failure = "MIT_VALIDATION_FINAL_CHECK_ERROR"
    if failure:
        print(json.dumps({"failure_code": failure}, ensure_ascii=True))
        print("REAL_MIT_JSON_VALIDATION=FAIL")
        return 1
    assert probe is not None
    print(probe.model_dump_json())
    print("MIT_SAMPLE_HASH_UNCHANGED=YES")
    print("MIT_DATABASE_UNCHANGED=YES")
    print("REAL_MIT_JSON_VALIDATION=PASS")
    return 0


class _SanitizedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        print('{"failure_code":"MIT_VALIDATION_ARGUMENT_ERROR"}')
        print("REAL_MIT_JSON_VALIDATION=FAIL")
        raise SystemExit(2)


def main() -> None:
    parser = _SanitizedArgumentParser(description="Read-only S11.2-A MIT JSON validation.")
    parser.add_argument("sample", type=Path)
    parser.add_argument("--expect-debits", type=int)
    parser.add_argument("--expect-tax", action="append", default=None)
    warning_group = parser.add_mutually_exclusive_group()
    warning_group.add_argument("--expect-warning", action="append", default=None)
    warning_group.add_argument("--expect-no-warnings", action="store_true")
    args = parser.parse_args()
    expected_warnings = (
        frozenset()
        if args.expect_no_warnings
        else (frozenset(args.expect_warning) if args.expect_warning is not None else None)
    )
    raise SystemExit(
        run_validation(
            args.sample,
            expected_debits=args.expect_debits,
            expected_taxes=(
                frozenset(args.expect_tax) if args.expect_tax is not None else None
            ),
            expected_warnings=expected_warnings,
        )
    )


if __name__ == "__main__":
    main()
