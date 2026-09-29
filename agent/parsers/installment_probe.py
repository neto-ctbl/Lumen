"""Read-only installment probe with allowlisted, non-fiscal stdout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.parsers.contracts import ExtractionStatus
from agent.parsers.installment_pdf import InstallmentFile, InstallmentPdfParser
from agent.parsers.runtime import DocumentParserRuntime, ParserRegistry


def sanitized_installment_summary(path: str | Path) -> dict[str, object]:
    result = DocumentParserRuntime(ParserRegistry((InstallmentPdfParser(),))).run_file(path)
    documents = (
        InstallmentFile.model_validate(result.structured_data).documents
        if result.document_family == "INSTALLMENT"
        else ()
    )
    checks = [document.validation.sum_matches_total for document in documents]
    return {
        "family": result.document_family,
        "matched": result.extraction_status is ExtractionStatus.MATCHED,
        "extraction_status": result.extraction_status.value,
        "documents_count": len(documents),
        "programs": sorted({document.program.value for document in documents}),
        "layouts": sorted({document.header.layout for document in documents}),
        "administrators": sorted({document.administrator.value for document in documents}),
        "debt_scopes": sorted({document.debt.scope.value for document in documents}),
        "identified_tax_count": len({tax for document in documents for tax in document.debt.taxes}),
        "components_count": sum(len(document.components) for document in documents),
        "has_taxpayer_id": bool(documents) and all(document.header.taxpayer_id for document in documents),
        "has_installment_reference": bool(documents) and all(
            document.installment.installment_reference
            or document.installment.agreement_number
            or document.installment.registration_number
            for document in documents
        ),
        "has_current_installment": bool(documents) and all(
            document.installment.current_installment is not None for document in documents
        ),
        "has_total_installments": bool(documents) and all(
            document.installment.total_installments is not None for document in documents
        ),
        "has_reference_period": bool(documents) and all(document.installment.reference_period for document in documents),
        "has_due_date": bool(documents) and all(document.payment.due_date for document in documents),
        "has_total": bool(documents) and all(document.payment.total_amount is not None for document in documents),
        "sum_matches_total": (
            False if False in checks else True if checks and all(check is True for check in checks) else None
        ),
        "warning_codes": list(result.warnings),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only sanitized installment-guide probe.")
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    print(json.dumps(sanitized_installment_summary(args.pdf), ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
