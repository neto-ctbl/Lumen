"""Content-first parser for text-layer DAS PDF documents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

from pydantic import BaseModel, ConfigDict
from pypdf import PdfReader
from unidecode import unidecode

from agent.parsers.contracts import (
    DocumentContext,
    DocumentSignal,
    ExtractionStatus,
    ParserExtraction,
    SignalProvenance,
    TechnicalFormat,
)


DAS_PARSER_NAME = "lumen.das-pdf"
DAS_PARSER_VERSION = "1"
_PDF_SIGNATURE = b"%PDF-"
_MONEY_RE = re.compile(r"(?<!\d)(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}(?!\d)")
_DATE_RE = re.compile(r"(?<!\d)(?P<day>0[1-9]|[12]\d|3[01])/(?P<month>0[1-9]|1[0-2])/(?P<year>\d{4})(?!\d)")
_CNPJ_RE = re.compile(r"(?<!\d)(?:\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14})(?!\d)")
_DOCUMENT_NUMBER_RE = re.compile(r"(?<!\d)\d[\d.\-/]{9,39}(?!\d)")
_COMPONENT_START_RE = re.compile(
    r"^(?P<code>\d{4,8})(?!\d)(?:\s*-?\s*(?P<denomination>.*))?$"
)
_MONTHS = {
    "JANEIRO": 1,
    "FEVEREIRO": 2,
    "MARCO": 3,
    "ABRIL": 4,
    "MAIO": 5,
    "JUNHO": 6,
    "JULHO": 7,
    "AGOSTO": 8,
    "SETEMBRO": 9,
    "OUTUBRO": 10,
    "NOVEMBRO": 11,
    "DEZEMBRO": 12,
}
_MONTH_NAME_RE = re.compile(
    rf"(?<![A-Z])(?P<month>{'|'.join(_MONTHS)})\s*/\s*(?P<year>\d{{4}})(?!\d)"
)
_NUMERIC_PERIOD_RE = re.compile(r"(?<!\d)(?P<month>0[1-9]|1[0-2])/(?P<year>\d{4})(?!\d)")
_KNOWN_LABELS = {
    "CNPJ",
    "RAZAO SOCIAL",
    "PERIODO DE APURACAO",
    "DATA DE VENCIMENTO",
    "NUMERO DO DOCUMENTO",
    "PAGAR ESTE DOCUMENTO ATE",
    "VALOR TOTAL DO DOCUMENTO",
    "COMPOSICAO DO DOCUMENTO DE ARRECADACAO",
}
_INSTALLMENT_OBSERVATION_MARKERS = (
    "PGFN",
    "SISPAR",
    "PARC",
    "PARCELAMENTO",
    "PARCELA",
    "PERT",
    "RELP",
)
_INSTALLMENT_COMPONENT_MARKERS = (
    "DIVIDA ATIVA",
    "DIV.ATIVA",
)


class DasHeader(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cnpj: str | None = None
    cnpj_structure_valid: bool | None = None
    corporate_name: str | None = None
    assessment_period: str | None = None
    due_date: str | None = None
    document_number: str | None = None
    pay_until: str | None = None
    total_amount: Decimal | None = None


class DasComponent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    denomination: str
    tax_family: str | None = None
    assessment_period: str | None = None
    state: str | None = None
    municipality: str | None = None
    principal_amount: Decimal | None = None
    penalty_amount: Decimal | None = None
    interest_amount: Decimal | None = None
    total_amount: Decimal | None = None


class DasValidation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    components_total_amount: Decimal | None = None
    sum_matches_total: bool | None = None
    pay_until_matches_due_date: bool | None = None


class DasDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    header: DasHeader
    components: tuple[DasComponent, ...]
    validation: DasValidation


@dataclass(frozen=True, slots=True)
class _PdfContent:
    status: ExtractionStatus
    text: str


class DasPdfParser:
    name = DAS_PARSER_NAME
    version = DAS_PARSER_VERSION
    supported_formats = frozenset({TechnicalFormat.PDF})

    def supports(self, document: DocumentContext) -> bool:
        if document.technical_format is not TechnicalFormat.PDF:
            return False
        content = _extract_pdf_content(document.file_path)
        return content.status is ExtractionStatus.MATCHED and _has_das_signature(content.text)

    def parse(self, document: DocumentContext) -> ParserExtraction:
        content = _extract_pdf_content(document.file_path)
        if content.status is ExtractionStatus.INVALID:
            return _empty_extraction(ExtractionStatus.INVALID, "INVALID_PDF")
        if content.status is ExtractionStatus.INCONCLUSIVE:
            return _empty_extraction(ExtractionStatus.INCONCLUSIVE, "PDF_TEXT_LAYER_MISSING")
        if not _has_das_signature(content.text):
            return _empty_extraction(ExtractionStatus.UNSUPPORTED, "DAS_SIGNATURE_NOT_FOUND")
        return parse_das_text(content.text)


def parse_das_text(text: str) -> ParserExtraction:
    """Parse already extracted text; intended for deterministic unit-level use."""
    if not _has_das_signature(text):
        return _empty_extraction(ExtractionStatus.UNSUPPORTED, "DAS_SIGNATURE_NOT_FOUND")

    lines = _clean_lines(text)
    searchable = "\n".join(_search_text(line) for line in lines)
    warnings: list[str] = []

    # Some official generators place all header labels after their values in the
    # PDF text stream.  Once the DAS signature is established, the first CNPJ
    # token in the document is a stronger signal than its extraction order.
    cnpj_match = _CNPJ_RE.search(searchable)
    cnpj_raw = cnpj_match.group(0) if cnpj_match is not None else None
    cnpj = _digits(cnpj_raw) if cnpj_raw else None
    cnpj_valid = _is_structurally_valid_cnpj(cnpj) if cnpj else None
    if cnpj is None:
        warnings.append("DAS_CNPJ_MISSING")
    elif not cnpj_valid:
        warnings.append("DAS_CNPJ_INVALID_STRUCTURE")

    corporate_name = _find_line_value(lines, "RAZAO SOCIAL")
    if corporate_name is None:
        warnings.append("DAS_CORPORATE_NAME_MISSING")

    assessment_period = _find_period_after_label(searchable, "PERIODO DE APURACAO")
    if assessment_period is None:
        warnings.append("DAS_ASSESSMENT_PERIOD_MISSING")

    due_date = _find_date_after_label(searchable, "DATA DE VENCIMENTO")
    if due_date is None:
        warnings.append("DAS_DUE_DATE_MISSING")

    document_number = _find_document_number(searchable)
    if document_number is None:
        warnings.append("DAS_DOCUMENT_NUMBER_MISSING")

    pay_until = _find_date_after_label(searchable, "PAGAR ESTE DOCUMENTO ATE")
    if pay_until is None:
        warnings.append("DAS_PAY_UNTIL_MISSING")

    total_amount = _find_money_after_label(searchable, "VALOR TOTAL DO DOCUMENTO")
    if total_amount is None:
        warnings.append("DAS_TOTAL_AMOUNT_MISSING")

    components, component_warnings = _parse_components(lines)
    warnings.extend(component_warnings)
    if not components:
        warnings.append("DAS_COMPONENTS_MISSING")

    component_totals = [component.total_amount for component in components]
    components_total = sum((value for value in component_totals if value is not None), Decimal("0.00"))
    has_all_component_totals = bool(components) and all(value is not None for value in component_totals)
    sum_matches_total = (
        abs(components_total - total_amount) <= Decimal("0.01")
        if total_amount is not None and has_all_component_totals
        else None
    )
    if sum_matches_total is False:
        warnings.append("DAS_COMPONENT_TOTAL_MISMATCH")

    pay_until_matches_due_date = pay_until == due_date if pay_until is not None and due_date is not None else None
    if pay_until_matches_due_date is False:
        warnings.append("DAS_PAY_UNTIL_DIFFERS_FROM_DUE_DATE")

    header = DasHeader(
        cnpj=cnpj,
        cnpj_structure_valid=cnpj_valid,
        corporate_name=corporate_name,
        assessment_period=assessment_period,
        due_date=due_date,
        document_number=document_number,
        pay_until=pay_until,
        total_amount=total_amount,
    )
    document = DasDocument(
        header=header,
        components=components,
        validation=DasValidation(
            components_total_amount=components_total if components else None,
            sum_matches_total=sum_matches_total,
            pay_until_matches_due_date=pay_until_matches_due_date,
        ),
    )
    confidence = _confidence(header, components, sum_matches_total)
    return ParserExtraction(
        document_family="DAS",
        extraction_status=ExtractionStatus.MATCHED,
        confidence=confidence,
        signals=_signals_from_header(header, confidence),
        warnings=tuple(dict.fromkeys(warnings)),
        structured_data={"document": document.model_dump(mode="json")},
    )


def _extract_pdf_content(path: Path) -> _PdfContent:
    try:
        with path.open("rb") as handle:
            if handle.read(len(_PDF_SIGNATURE)) != _PDF_SIGNATURE:
                return _PdfContent(ExtractionStatus.INVALID, "")
        reader = PdfReader(str(path))
        if reader.is_encrypted or len(reader.pages) == 0:
            return _PdfContent(ExtractionStatus.INVALID, "")
        # Layout mode preserves column boundaries used by the official DAS
        # composition table while still reading only the embedded text layer.
        pages = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    except Exception:
        return _PdfContent(ExtractionStatus.INVALID, "")
    text = "\n".join(pages)
    if not text.strip():
        return _PdfContent(ExtractionStatus.INCONCLUSIVE, "")
    return _PdfContent(ExtractionStatus.MATCHED, text)


def _has_das_signature(text: str) -> bool:
    normalized = _search_text(text)
    title = "DOCUMENTO DE ARRECADACAO" in normalized and "SIMPLES NACIONAL" in normalized
    structural_markers = sum(
        marker in normalized
        for marker in (
            "PERIODO DE APURACAO",
            "COMPOSICAO DO DOCUMENTO DE ARRECADACAO",
            "VALOR TOTAL DO DOCUMENTO",
            "PAGAR ESTE DOCUMENTO ATE",
        )
    )
    return title and structural_markers >= 2 and not _has_installment_signature(normalized)


def _has_installment_signature(normalized: str) -> bool:
    observation_index = normalized.find("OBSERVACOES")
    composition_index = normalized.find("COMPOSICAO DO DOCUMENTO DE ARRECADACAO")
    if observation_index >= 0:
        observation_end = composition_index if composition_index > observation_index else len(normalized)
        observation = normalized[observation_index + len("OBSERVACOES") : observation_end]
        if any(re.search(rf"\b{re.escape(marker)}\b", observation) for marker in _INSTALLMENT_OBSERVATION_MARKERS):
            return True

    if composition_index < 0:
        return False
    composition = normalized[composition_index:]
    return any(marker in composition for marker in _INSTALLMENT_COMPONENT_MARKERS)


def _clean_lines(text: str) -> list[str]:
    return [cleaned for line in text.splitlines() if (cleaned := " ".join(line.replace("\xa0", " ").split()))]


def _search_text(value: str) -> str:
    return " ".join(unidecode(value).upper().split())


def _find_after_label(searchable: str, label: str, pattern: re.Pattern[str], *, span: int = 400) -> str | None:
    label_index = searchable.find(label)
    if label_index < 0:
        return None
    match = pattern.search(searchable[label_index + len(label) : label_index + len(label) + span])
    return match.group(0) if match is not None else None


def _find_line_value(lines: list[str], label: str) -> str | None:
    for index, line in enumerate(lines):
        normalized = _search_text(line)
        if label not in normalized:
            continue
        label_match = re.search(re.escape(label), normalized)
        assert label_match is not None
        if ":" in line and normalized.startswith(label):
            candidate = " ".join(line.split(":", maxsplit=1)[1].split())
            if candidate:
                return candidate
        remainder = normalized[label_match.end() :].lstrip(" :-")
        if remainder and not any(known in remainder for known in _KNOWN_LABELS - {label}):
            return remainder
        if index + 1 < len(lines):
            candidate = _CNPJ_RE.sub("", lines[index + 1]).strip(" -|")
            if not any(_search_text(candidate).startswith(known) for known in _KNOWN_LABELS):
                return " ".join(candidate.split()) or None
    return None


def _find_period_after_label(searchable: str, label: str) -> str | None:
    fragment = _fragment_after_label(searchable, label)
    return _find_period(fragment)


def _find_period(value: str) -> str | None:
    month_name = _MONTH_NAME_RE.search(value)
    if month_name is not None:
        return f"{int(month_name.group('year')):04d}-{_MONTHS[month_name.group('month')]:02d}"
    numeric = _NUMERIC_PERIOD_RE.search(value)
    if numeric is not None:
        return f"{int(numeric.group('year')):04d}-{int(numeric.group('month')):02d}"
    return None


def _find_date_after_label(searchable: str, label: str) -> str | None:
    match = _DATE_RE.search(_fragment_after_label(searchable, label))
    if match is None:
        return None
    try:
        return date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        ).isoformat()
    except ValueError:
        return None


def _find_document_number(searchable: str) -> str | None:
    fragment = _fragment_after_label(searchable, "NUMERO DO DOCUMENTO")
    for match in _DOCUMENT_NUMBER_RE.finditer(fragment):
        candidate = match.group(0)
        if _DATE_RE.fullmatch(candidate) is None and _NUMERIC_PERIOD_RE.fullmatch(candidate) is None:
            return candidate
    return None


def _find_money_after_label(searchable: str, label: str) -> Decimal | None:
    match = _MONEY_RE.search(_fragment_after_label(searchable, label))
    return _parse_money(match.group(0)) if match is not None else None


def _fragment_after_label(searchable: str, label: str, *, span: int = 500) -> str:
    index = searchable.find(label)
    return "" if index < 0 else searchable[index + len(label) : index + len(label) + span]


def _parse_components(lines: list[str]) -> tuple[tuple[DasComponent, ...], list[str]]:
    start = next(
        (index for index, line in enumerate(lines) if "COMPOSICAO DO DOCUMENTO DE ARRECADACAO" in _search_text(line)),
        None,
    )
    if start is None:
        return (), []
    body = lines[start + 1 :]
    totals_index = next(
        (index for index, line in enumerate(body) if _search_text(line).startswith("TOTAIS")),
        None,
    )
    if totals_index is not None:
        body = body[:totals_index]
    component_starts: list[tuple[int, re.Match[str]]] = []
    for index, line in enumerate(body):
        match = _COMPONENT_START_RE.fullmatch(_search_text(line))
        if match is not None:
            component_starts.append((index, match))

    components: list[DasComponent] = []
    warnings: list[str] = []
    for position, (line_index, match) in enumerate(component_starts):
        end = component_starts[position + 1][0] if position + 1 < len(component_starts) else len(body)
        group = body[line_index:end]
        component, complete = _parse_component_group(match, group)
        components.append(component)
        if not complete:
            warnings.append("DAS_COMPONENT_AMOUNTS_INCOMPLETE")
    return tuple(components), warnings


def _parse_component_group(match: re.Match[str], group: list[str]) -> tuple[DasComponent, bool]:
    searchable_group = "\n".join(_search_text(line) for line in group)
    denomination = (match.group("denomination") or "").strip(" -")
    if not denomination:
        denomination_parts: list[str] = []
        for line in group[1:]:
            normalized = _search_text(line)
            if _find_period(normalized) is not None or _MONEY_RE.search(normalized) is not None:
                break
            denomination_parts.append(line)
        denomination = " ".join(denomination_parts)
    denomination = _trim_denomination(denomination)
    family = _tax_family(denomination)
    amounts = [_parse_money(value) for value in _MONEY_RE.findall(searchable_group)]
    selected, complete = _component_amounts(amounts)
    state = _extract_state(searchable_group, family)
    municipality = _extract_municipality(" ".join(group), family)
    return (
        DasComponent(
            code=match.group("code"),
            denomination=denomination or "UNKNOWN",
            tax_family=family,
            assessment_period=_find_period(searchable_group),
            state=state,
            municipality=municipality,
            principal_amount=selected[0],
            penalty_amount=selected[1],
            interest_amount=selected[2],
            total_amount=selected[3],
        ),
        complete,
    )


def _component_amounts(amounts: list[Decimal]) -> tuple[list[Decimal | None], bool]:
    if len(amounts) >= 4:
        return list(amounts[-4:]), True
    if len(amounts) == 2:
        # Official DAS PDFs render empty Multa/Juros cells when both are zero.
        return [amounts[0], Decimal("0.00"), Decimal("0.00"), amounts[1]], True
    return [*amounts, *([None] * (4 - len(amounts)))], False


def _trim_denomination(value: str) -> str:
    normalized = " ".join(value.split())
    cut_positions = [
        match.start()
        for pattern in (_MONTH_NAME_RE, _NUMERIC_PERIOD_RE, _MONEY_RE)
        if (match := pattern.search(_search_text(normalized))) is not None
    ]
    return normalized[: min(cut_positions)].strip(" -|") if cut_positions else normalized.strip(" -|")


def _tax_family(denomination: str) -> str | None:
    normalized = _search_text(denomination)
    for marker, family in (
        ("COFINS", "COFINS"),
        ("CSLL", "CSLL"),
        ("IRPJ", "IRPJ"),
        ("PIS", "PIS"),
        ("INSS", "INSS"),
        ("ICMS", "ICMS"),
        ("ISS", "ISS"),
    ):
        if re.search(rf"\b{marker}\b", normalized):
            return family
    return None


def _extract_state(value: str, family: str | None) -> str | None:
    labeled = re.search(r"\bUF\s*:?\s*(?P<state>[A-Z]{2})\b", value)
    if labeled is not None:
        return labeled.group("state")
    parenthetical = re.search(r"\((?P<state>[A-Z]{2})\)\s*-\s*\d{2}/\d{4}", value)
    if parenthetical is not None:
        return parenthetical.group("state")
    if family == "ICMS":
        trailing = re.search(r"(?:^|\s)(?P<state>[A-Z]{2})\s*-\s*\d{2}/\d{4}", value)
        if trailing is not None:
            return trailing.group("state")
    return None


def _extract_municipality(value: str, family: str | None) -> str | None:
    normalized = " ".join(value.split())
    match = re.search(
        r"MUNIC[IÍ]PIO\s*:?\s*(?P<municipality>.+?)(?=\s+UF\s*:?|\s+\d{2}/\d{4}|\s+\d[\d.]*,\d{2}|$)",
        normalized,
        flags=re.IGNORECASE,
    )
    if match is not None:
        return " ".join(match.group("municipality").strip(" -|").split())
    if family != "ISS":
        return None
    unlabeled = re.search(
        r"(?P<municipality>[A-Z][A-Z\s.'-]+?)\s*\([A-Z]{2}\)\s*-\s*\d{2}/\d{4}",
        _search_text(value),
    )
    return " ".join(unlabeled.group("municipality").split()) if unlabeled is not None else None


def _parse_money(value: str) -> Decimal:
    try:
        return Decimal(value.replace(".", "").replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("invalid Brazilian monetary value") from exc


def _digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def _is_structurally_valid_cnpj(value: str) -> bool:
    if len(value) != 14 or not value.isdigit() or value == value[0] * 14:
        return False
    first = _cnpj_digit(value[:12], (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    second = _cnpj_digit(value[:12] + str(first), (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return value.endswith(f"{first}{second}")


def _cnpj_digit(value: str, weights: tuple[int, ...]) -> int:
    remainder = sum(int(digit) * weight for digit, weight in zip(value, weights, strict=True)) % 11
    return 0 if remainder < 2 else 11 - remainder


def _confidence(header: DasHeader, components: tuple[DasComponent, ...], sum_matches: bool | None) -> float:
    score = Decimal("0.40")
    score += Decimal("0.10") if header.cnpj_structure_valid else Decimal("0")
    score += Decimal("0.10") if header.assessment_period else Decimal("0")
    score += Decimal("0.08") if header.due_date else Decimal("0")
    score += Decimal("0.08") if header.document_number else Decimal("0")
    score += Decimal("0.08") if header.total_amount is not None else Decimal("0")
    score += Decimal("0.08") if components else Decimal("0")
    score += Decimal("0.08") if sum_matches is True else Decimal("0")
    return float(min(score, Decimal("1.00")))


def _signals_from_header(header: DasHeader, confidence: float) -> tuple[DocumentSignal, ...]:
    values = (
        ("cnpj", header.cnpj),
        ("razao_social", header.corporate_name),
        ("period_from_content", header.assessment_period),
        ("due_date", header.due_date),
        ("document_number", header.document_number),
        ("pay_until", header.pay_until),
        ("amount_total", str(header.total_amount) if header.total_amount is not None else None),
    )
    return tuple(
        DocumentSignal(name=name, value=value, provenance=SignalProvenance.CONTENT, confidence=confidence)
        for name, value in values
        if value is not None
    )


def _empty_extraction(status: ExtractionStatus, warning: str) -> ParserExtraction:
    return ParserExtraction(
        document_family="UNKNOWN",
        extraction_status=status,
        confidence=None,
        warnings=(warning,),
    )
