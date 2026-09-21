"""Read-only DARF-only harness; stdout contains only allowlisted summary metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.parsers.contracts import ExtractionStatus
from agent.parsers.darf_pdf import DarfFile, DarfPdfParser
from agent.parsers.runtime import DocumentParserRuntime, ParserRegistry


def sanitized_darf_summary(path: str | Path) -> dict[str, object]:
    result = DocumentParserRuntime(ParserRegistry((DarfPdfParser(),))).run_file(path)
    documents = DarfFile.model_validate(result.structured_data).documents if result.document_family == "DARF" else ()
    rows = [row for doc in documents for row in doc.revenues]
    checks = [doc.validation.sum_matches_total for doc in documents]
    return {
        "family": result.document_family,
        "matched": result.extraction_status is ExtractionStatus.MATCHED,
        "extraction_status": result.extraction_status.value,
        "documents_count": len(documents),
        "revenues_count": len(rows),
        "identified_tax_count": sum(row.tax != "UNKNOWN" for row in rows),
        "taxes": sorted({row.tax for row in rows}),
        "period_kinds": sorted({doc.header.assessment_period.kind.value for doc in documents if doc.header.assessment_period}),
        "has_taxpayer_id": bool(documents) and all(doc.header.taxpayer_id for doc in documents),
        "has_assessment_period": bool(documents) and all(doc.header.assessment_period for doc in documents),
        "has_due_date": bool(documents) and all(doc.header.due_date for doc in documents),
        "has_document_number": bool(documents) and all(doc.header.document_number for doc in documents),
        "has_total": bool(documents) and all(doc.header.total_amount is not None for doc in documents),
        "sum_matches_total": False if False in checks else True if checks and all(check is True for check in checks) else None,
        "warning_codes": list(result.warnings),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a read-only sanitized DARF PDF probe.")
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    print(json.dumps(sanitized_darf_summary(args.pdf), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
