from __future__ import annotations

import json
from pathlib import Path

from agent.parsers.contracts import (
    DocumentContext,
    DocumentSignal,
    ExtractionStatus,
    SignalProvenance,
    TechnicalFormat,
)
from agent.parsers.known_layouts import (
    DAS_FORM_LAYOUT_ID,
    FEDERAL_REVENUE_FORM_LAYOUT_ID,
    GO_DARE_51_LAYOUT_ID,
    FederalRevenueFormExtractor,
    GoDare51LayoutExtractor,
    StateRevenueClassifier,
)
from agent.parsers.iss_guide import ANAPOLIS_DUAM_LAYOUT_ID, NEROPOLIS_DUAM_LAYOUT_ID
from agent.parsers.legacy_darf import LEGACY_DARF_FORM_LAYOUT_ID
from agent.parsers.mit_json import MIT_JSON_LAYOUT_ID
from agent.parsers.layout_framework import (
    ClassificationResult,
    ComposableDocumentParser,
    DocumentClassifier,
    DocumentLayoutDetector,
    DocumentLayoutExtractor,
    LayoutExtractionFailure,
    LayoutRegistry,
    default_layout_registry,
    sanitized_layout_diagnostic,
)
from agent.parsers.runtime import DocumentParserRuntime, ParserRegistry, default_parser_registry
from agent.parsers.state_revenue_guide import StateRevenue
from backend.tests.test_darf_pdf_parser import _write as write_darf_pdf
from backend.tests.test_das_pdf_parser import _write_das as write_das_pdf
from backend.tests.test_state_guide_pdf_parser import _write as write_state_pdf
from backend.tests.watcher_agent_test_utils import write_synthetic_pdf


class SyntheticLayoutExtractor:
    layout_id = "SYNTHETIC_FORM"

    def supports_layout(self, context: DocumentContext) -> bool:
        payload = json.loads(context.file_path.read_text(encoding="utf-8"))
        return payload.get("layout") == self.layout_id

    def extract(self, context: DocumentContext) -> dict[str, object]:
        payload = json.loads(context.file_path.read_text(encoding="utf-8"))
        outcome = payload.get("outcome")
        if outcome == "unsupported":
            raise LayoutExtractionFailure(ExtractionStatus.UNSUPPORTED, "SYNTHETIC_UNSUPPORTED")
        if outcome == "invalid":
            raise LayoutExtractionFailure(ExtractionStatus.INVALID, "SYNTHETIC_INVALID")
        if outcome == "inconclusive":
            raise LayoutExtractionFailure(ExtractionStatus.INCONCLUSIVE, "SYNTHETIC_INCONCLUSIVE")
        if outcome == "explode":
            raise RuntimeError("sensitive extracted content")
        return {"structural_code": str(payload.get("structural_code", "UNKNOWN"))}


class SyntheticClassifier:
    def classify(
        self,
        extracted: dict[str, object],
        context: DocumentContext,
    ) -> ClassificationResult:
        del context
        code = str(extracted["structural_code"])
        if code == "EXPLODE":
            raise RuntimeError("sensitive classification content")
        known = code == "KNOWN"
        return ClassificationResult(
            classification_id="SYNTHETIC_KIND" if known else "UNKNOWN",
            classification_known=known,
            document_family="SYNTHETIC_DOCUMENT" if known else "UNKNOWN",
            document_kind="SYNTHETIC_KIND" if known else "UNKNOWN",
            confidence=0.93 if known else 0.41,
            signals=(
                DocumentSignal(
                    name="synthetic_structure_present",
                    value=True,
                    provenance=SignalProvenance.CONTENT,
                    confidence=0.93 if known else 0.41,
                ),
            ),
            warnings=() if known else ("UNKNOWN_CLASSIFICATION",),
        )


class ExplodingDetector(SyntheticLayoutExtractor):
    layout_id = "EXPLODING_FORM"

    def supports_layout(self, context: DocumentContext) -> bool:
        del context
        raise RuntimeError("sensitive detector content")


def _path(tmp_path: Path, **payload: object) -> Path:
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps({"layout": "SYNTHETIC_FORM", **payload}), encoding="utf-8")
    return path


def _context(path: Path, technical_format: TechnicalFormat = TechnicalFormat.JSON) -> DocumentContext:
    return DocumentContext(file_path=path, technical_format=technical_format)


def _parser(
    extractor: SyntheticLayoutExtractor | None = None,
    classifier: SyntheticClassifier | None = None,
) -> ComposableDocumentParser[dict[str, object]]:
    return ComposableDocumentParser(
        name="synthetic.composed",
        version="1",
        supported_formats=frozenset({TechnicalFormat.JSON}),
        extractor=extractor or SyntheticLayoutExtractor(),
        classifier=classifier or SyntheticClassifier(),
        serialize_extracted=lambda extracted: {"extracted": extracted},
    )


def test_protocols_and_explicit_registry_identify_known_layout(tmp_path: Path) -> None:
    extractor = SyntheticLayoutExtractor()
    classifier = SyntheticClassifier()
    assert isinstance(extractor, DocumentLayoutDetector)
    assert isinstance(extractor, DocumentLayoutExtractor)
    assert isinstance(classifier, DocumentClassifier)

    registry = LayoutRegistry((extractor,))
    identified = registry.identify(_context(_path(tmp_path)))

    assert registry.layout_ids == ("SYNTHETIC_FORM",)
    assert identified.layout_id == "SYNTHETIC_FORM"
    assert identified.matched is True and identified.confidence == 1
    assert identified.technical_format is TechnicalFormat.JSON
    assert identified.signals[0].provenance is SignalProvenance.FILE_STRUCTURE


def test_registry_rejects_duplicate_layout_id() -> None:
    registry = LayoutRegistry((SyntheticLayoutExtractor(),))
    try:
        registry.register(SyntheticLayoutExtractor())
    except ValueError as exc:
        assert str(exc) == "layout already registered: SYNTHETIC_FORM"
    else:
        raise AssertionError("duplicate layout registration was accepted")


def test_unknown_layout_is_distinct_and_detector_errors_are_sanitized(tmp_path: Path) -> None:
    registry = LayoutRegistry((ExplodingDetector(), SyntheticLayoutExtractor()))
    path = tmp_path / "DARF ICMS 08-2026.json"
    path.write_text(json.dumps({"layout": "NEW_FORM"}), encoding="utf-8")

    identified = registry.identify(_context(path))

    assert identified.layout_id == "UNKNOWN" and identified.matched is False
    assert identified.confidence is None
    assert identified.warnings == ("LAYOUT_DETECTOR_ERROR", "UNKNOWN_GUIDE_LAYOUT")
    assert "sensitive" not in identified.model_dump_json()


def test_composed_parser_matches_with_standard_result_and_runtime_unchanged(tmp_path: Path) -> None:
    runtime = DocumentParserRuntime(ParserRegistry((_parser(),)))
    result = runtime.run_file(_path(tmp_path, structural_code="KNOWN"))

    assert result.parser_name == "synthetic.composed" and result.parser_version == "1"
    assert result.extraction_status is ExtractionStatus.MATCHED
    assert result.document_family == "SYNTHETIC_DOCUMENT" and result.confidence == 0.93
    assert result.structured_data == {"extracted": {"structural_code": "KNOWN"}}
    signals = {signal.name: signal for signal in result.signals}
    assert signals["layout_id"].value == "SYNTHETIC_FORM"
    assert signals["layout_id"].provenance is SignalProvenance.FILE_STRUCTURE
    assert signals["classification_id"].value == "SYNTHETIC_KIND"
    assert signals["classification_known"].value is True
    assert signals["synthetic_structure_present"].provenance is SignalProvenance.CONTENT


def test_composed_parser_can_serialize_extraction_with_classification(tmp_path: Path) -> None:
    parser = ComposableDocumentParser(
        name="synthetic.combined",
        version="1",
        supported_formats=frozenset({TechnicalFormat.JSON}),
        extractor=SyntheticLayoutExtractor(),
        classifier=SyntheticClassifier(),
        serialize_extracted=lambda extracted: {"unused": extracted},
        serialize_result=lambda extracted, classification: {
            "structural_code": str(extracted["structural_code"]),
            "classification": classification.classification_id,
        },
    )
    result = parser.parse(_context(_path(tmp_path, structural_code="KNOWN")))
    assert result.structured_data == {
        "structural_code": "KNOWN",
        "classification": "SYNTHETIC_KIND",
    }


def test_known_layout_unknown_classification_preserves_extraction(tmp_path: Path) -> None:
    result = _parser().parse(_context(_path(tmp_path, structural_code="NEW_CODE")))

    assert result.extraction_status is ExtractionStatus.MATCHED
    assert result.document_family == "UNKNOWN" and result.confidence == 0.41
    assert result.structured_data == {"extracted": {"structural_code": "NEW_CODE"}}
    assert result.warnings == ("UNKNOWN_CLASSIFICATION",)
    signals = {signal.name: signal.value for signal in result.signals}
    assert signals["layout_id"] == "SYNTHETIC_FORM"
    assert signals["classification_id"] == "UNKNOWN"
    assert signals["classification_known"] is False


def test_unknown_layout_is_unsupported_even_with_deceptive_filename(tmp_path: Path) -> None:
    path = tmp_path / "DARF ICMS DAS 08-2026.json"
    path.write_text(json.dumps({"layout": "NEW_FORM", "structural_code": "KNOWN"}), encoding="utf-8")

    result = _parser().parse(_context(path))

    assert result.extraction_status is ExtractionStatus.UNSUPPORTED
    assert result.document_family == "UNKNOWN"
    assert result.warnings == ("UNKNOWN_GUIDE_LAYOUT",)
    assert result.signals[0].value == "UNKNOWN"


def test_composed_parser_maps_expected_extraction_outcomes(tmp_path: Path) -> None:
    for outcome, status, warning in (
        ("unsupported", ExtractionStatus.UNSUPPORTED, "SYNTHETIC_UNSUPPORTED"),
        ("invalid", ExtractionStatus.INVALID, "SYNTHETIC_INVALID"),
        ("inconclusive", ExtractionStatus.INCONCLUSIVE, "SYNTHETIC_INCONCLUSIVE"),
    ):
        result = _parser().parse(_context(_path(tmp_path, outcome=outcome)))
        assert result.extraction_status is status
        assert result.warnings == (warning,)
        assert result.signals[0].value == "SYNTHETIC_FORM"


def test_extractor_and_classifier_exceptions_are_sanitized(tmp_path: Path) -> None:
    extraction_error = _parser().parse(_context(_path(tmp_path, outcome="explode")))
    classification_error = _parser().parse(_context(_path(tmp_path, structural_code="EXPLODE")))

    assert extraction_error.extraction_status is ExtractionStatus.ERROR
    assert extraction_error.warnings == ("LAYOUT_EXTRACTION_ERROR",)
    assert classification_error.extraction_status is ExtractionStatus.ERROR
    assert classification_error.warnings == ("DOCUMENT_CLASSIFICATION_ERROR",)
    assert "sensitive" not in extraction_error.model_dump_json()
    assert "sensitive" not in classification_error.model_dump_json()


def test_wrong_format_is_unsupported_before_extraction(tmp_path: Path) -> None:
    result = _parser().parse(_context(_path(tmp_path), TechnicalFormat.XML))
    assert result.extraction_status is ExtractionStatus.UNSUPPORTED
    assert result.warnings == ("LAYOUT_FORMAT_UNSUPPORTED",)


def test_sanitized_unknown_pdf_diagnostic_has_no_path_or_content(tmp_path: Path) -> None:
    path = tmp_path / "DARF ICMS DAS empresa valor 08-2026.pdf"
    write_synthetic_pdf(path, text="FORMULARIO TOTALMENTE NOVO DADO SENSIVEL SINTETICO")

    diagnostic = sanitized_layout_diagnostic(path, default_layout_registry())
    serialized = diagnostic.model_dump_json()

    assert diagnostic.technical_format == "PDF" and diagnostic.page_count == 1
    assert diagnostic.text_available is True and diagnostic.known_layout is False
    assert diagnostic.layout_id == diagnostic.classification == "UNKNOWN"
    assert diagnostic.classification_known is False
    assert diagnostic.extraction_status is ExtractionStatus.UNSUPPORTED
    assert diagnostic.warning_codes == ("UNKNOWN_GUIDE_LAYOUT",)
    assert str(path) not in serialized and "SENSIVEL" not in serialized and "empresa" not in serialized


def test_default_layout_registry_is_explicit_and_deterministic() -> None:
    assert default_layout_registry().layout_ids == (
        DAS_FORM_LAYOUT_ID,
        FEDERAL_REVENUE_FORM_LAYOUT_ID,
        GO_DARE_51_LAYOUT_ID,
        LEGACY_DARF_FORM_LAYOUT_ID,
        ANAPOLIS_DUAM_LAYOUT_ID,
        NEROPOLIS_DUAM_LAYOUT_ID,
        MIT_JSON_LAYOUT_ID,
    )


def test_existing_layout_adapters_recognize_and_extract_without_fiscal_reclassification(
    tmp_path: Path,
) -> None:
    registry = default_layout_registry()
    das = write_das_pdf(tmp_path, name="das-form.pdf")
    assert registry.identify(_context(das, TechnicalFormat.PDF)).layout_id == DAS_FORM_LAYOUT_ID

    darf = write_darf_pdf(tmp_path)
    darf_context = _context(darf, TechnicalFormat.PDF)
    assert registry.identify(darf_context).layout_id == FEDERAL_REVENUE_FORM_LAYOUT_ID
    federal = FederalRevenueFormExtractor().extract(darf_context)
    assert len(federal.documents) == 1 and federal.documents[0].guide.revenues

    dare = write_state_pdf(tmp_path, filename="dare-form.pdf")
    dare_context = _context(dare, TechnicalFormat.PDF)
    assert registry.identify(dare_context).layout_id == GO_DARE_51_LAYOUT_ID
    state = GoDare51LayoutExtractor().extract(dare_context)
    assert len(state.documents) == 1 and state.documents[0].guide.revenues


def test_dare_installment_is_known_layout_but_not_normal_state_classification(tmp_path: Path) -> None:
    path = write_state_pdf(tmp_path, installment="01", filename="ICMS normal.pdf")
    context = _context(path, TechnicalFormat.PDF)

    identified = default_layout_registry().identify(context)
    parsed = DocumentParserRuntime(default_parser_registry()).run_file(path)

    assert identified.layout_id == GO_DARE_51_LAYOUT_ID and identified.matched is True
    assert parsed.extraction_status is ExtractionStatus.UNSUPPORTED
    assert parsed.document_family == "UNKNOWN"


def test_state_known_layout_unknown_classification_preserves_revenue() -> None:
    revenue = StateRevenue(revenue_code="9999", description="RECEITA NAO MAPEADA")
    result = StateRevenueClassifier().classify(
        revenue,
        DocumentContext(file_path=Path("synthetic.pdf"), technical_format=TechnicalFormat.PDF),
    )

    assert revenue.revenue_code == "9999" and revenue.description == "RECEITA NAO MAPEADA"
    assert result.classification_id == "UNKNOWN" and result.classification_known is False
    assert result.document_family == "STATE_GUIDE" and result.document_kind == "UNKNOWN"
    assert "STATE_REVENUE_CODE_UNKNOWN" in result.warnings
    assert "STATE_GUIDE_KIND_INCONCLUSIVE" in result.warnings
