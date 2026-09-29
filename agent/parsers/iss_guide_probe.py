"""Read-only ISS-guide probe with strictly allowlisted aggregate output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.parsers.contracts import ExtractionStatus
from agent.parsers.iss_guide import IssGuideFile, IssGuidePdfParser
from agent.parsers.runtime import DocumentParserRuntime, ParserRegistry


def sanitized_iss_summary(path: str | Path) -> dict[str, object]:
    result = DocumentParserRuntime(ParserRegistry((IssGuidePdfParser(),))).run_file(path)
    documents = (
        IssGuideFile.model_validate(result.structured_data).documents
        if result.document_family == "ISS_GUIDE"
        else ()
    )
    layouts = sorted({document.header.layout for document in documents})
    classifications = sorted({document.classification.classification for document in documents})
    checks = [document.validation.sum_matches_total for document in documents]
    return {
        "family": result.document_family,
        "layout_id": layouts[0] if len(layouts) == 1 else "MULTIPLE" if layouts else "UNKNOWN",
        "layout_known": bool(layouts),
        "matched": result.extraction_status is ExtractionStatus.MATCHED,
        "extraction_status": result.extraction_status.value,
        "documents_count": len(documents),
        "classifications": classifications,
        "has_taxpayer_id": bool(documents) and all(document.header.taxpayer_id for document in documents),
        "has_municipal_registration": bool(documents) and all(
            document.header.municipal_registration for document in documents
        ),
        "has_reference_period": bool(documents) and all(
            document.header.reference_period
            or any(revenue.reference_period for revenue in document.revenues)
            for document in documents
        ),
        "has_due_date": bool(documents) and all(document.header.due_date for document in documents),
        "has_document_number": bool(documents) and all(
            document.header.document_number for document in documents
        ),
        "has_total": bool(documents) and all(
            document.header.total_amount is not None for document in documents
        ),
        "components_count": sum(
            len(revenue.components) for document in documents for revenue in document.revenues
        ),
        "sum_matches_total": (
            False if False in checks else True if checks and all(check is True for check in checks) else None
        ),
        "warning_codes": list(result.warnings),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only sanitized municipal ISS-guide probe.")
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    print(json.dumps(sanitized_iss_summary(args.pdf), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
