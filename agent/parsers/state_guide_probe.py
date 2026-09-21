"""Read-only state-only probe with allowlisted, non-fiscal stdout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.parsers.contracts import ExtractionStatus
from agent.parsers.runtime import DocumentParserRuntime, ParserRegistry
from agent.parsers.state_guide_pdf import StateGuideFile, StateGuidePdfParser
from agent.parsers.state_revenue_codes import is_known_state_code


def sanitized_state_summary(path: str | Path) -> dict[str, object]:
    result = DocumentParserRuntime(ParserRegistry((StateGuidePdfParser(),))).run_file(path)
    documents = StateGuideFile.model_validate(result.structured_data).documents if result.document_family == "STATE_GUIDE" else ()
    checks = [doc.validation.sum_matches_total for doc in documents]
    return {
        "family": result.document_family,
        "matched": result.extraction_status is ExtractionStatus.MATCHED,
        "extraction_status": result.extraction_status.value,
        "documents_count": len(documents),
        "guide_kinds": sorted({doc.guide_kind for doc in documents}),
        "revenue_codes_known_count": sum(is_known_state_code(row.revenue_code, row.parent_revenue_code) for doc in documents for row in doc.revenues),
        "has_taxpayer_id": bool(documents) and all(doc.header.taxpayer_id for doc in documents),
        "has_state_registration": bool(documents) and all(doc.header.state_registration for doc in documents),
        "has_reference_period": bool(documents) and all(doc.header.reference_period for doc in documents),
        "has_due_date": bool(documents) and all(doc.header.due_date for doc in documents),
        "has_document_number": bool(documents) and all(doc.header.document_number for doc in documents),
        "has_total": bool(documents) and all(doc.header.total_amount is not None for doc in documents),
        "sum_matches_total": False if False in checks else True if checks and all(check is True for check in checks) else None,
        "warning_codes": list(result.warnings),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only sanitized state-guide probe.")
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    print(json.dumps(sanitized_state_summary(args.pdf), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
