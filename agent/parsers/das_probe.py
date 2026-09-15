"""Read-only and sanitized local DAS parser harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.parsers.contracts import ExtractionStatus
from agent.parsers.runtime import DocumentParserRuntime, default_parser_registry


def sanitized_das_summary(path: str | Path) -> dict[str, object]:
    result = DocumentParserRuntime(default_parser_registry()).run_file(path)
    document = result.structured_data.get("document")
    document_data = document if isinstance(document, dict) else {}
    header = document_data.get("header")
    header_data = header if isinstance(header, dict) else {}
    components = document_data.get("components")
    component_rows = components if isinstance(components, list) else []
    validation = document_data.get("validation")
    validation_data = validation if isinstance(validation, dict) else {}
    return {
        "family": result.document_family,
        "matched": result.extraction_status is ExtractionStatus.MATCHED,
        "extraction_status": result.extraction_status.value,
        "components_count": len(component_rows),
        "has_cnpj": bool(header_data.get("cnpj")),
        "has_assessment_period": bool(header_data.get("assessment_period")),
        "has_due_date": bool(header_data.get("due_date")),
        "has_document_number": bool(header_data.get("document_number")),
        "has_total": header_data.get("total_amount") is not None,
        "sum_matches_total": validation_data.get("sum_matches_total"),
        "warning_codes": list(result.warnings),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a read-only sanitized DAS PDF probe.")
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    print(json.dumps(sanitized_das_summary(args.pdf), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
