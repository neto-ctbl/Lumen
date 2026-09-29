"""Structural extraction for the classic numbered-field DARF form.

The layout is fiscal-family agnostic.  In S11 it is consumed by the
installment parser; the revenue code is interpreted only by that classifier.
"""

from __future__ import annotations

from decimal import Decimal
import re

from pydantic import BaseModel, ConfigDict
from unidecode import unidecode

from agent.parsers.contracts import DocumentContext, ExtractionStatus, TechnicalFormat
from agent.parsers.federal_revenue_guide import GuidePeriod, parse_guide_period
from agent.parsers.guide_common import (
    CNPJ_RE,
    CPF_RE,
    MONEY_RE,
    digits,
    parse_date,
    parse_money,
    read_pdf_pages,
    search_text,
    valid_cnpj,
    valid_cpf,
)
from agent.parsers.layout_framework import LayoutExtractionFailure

LEGACY_DARF_FORM_LAYOUT_ID = "DARF_LEGACY_FORM"

_FIELD_LABELS = (
    "NOME / TELEFONE",
    "NOME/TELEFONE",
    "NOME / RAZAO SOCIAL",
    "NOME/RAZAO SOCIAL",
    "PERIODO DE APURACAO",
    "NUMERO DO CPF OU CNPJ",
    "NUMERO DO CPF/CNPJ",
    "CODIGO DA RECEITA",
    "NUMERO DE REFERENCIA",
    "DATA DE VENCIMENTO",
    "VALOR DO PRINCIPAL",
    "VALOR DA MULTA",
    "VALOR DOS JUROS",
    "VALOR TOTAL",
    "DATA LIMITE PARA ACOLHIMENTO",
    "AUTENTICACAO BANCARIA",
)


class LegacyDarfModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LegacyDarfHeader(LegacyDarfModel):
    taxpayer_id: str | None = None
    taxpayer_id_kind: str | None = None
    taxpayer_id_structure_valid: bool | None = None
    taxpayer_name: str | None = None
    assessment_period: GuidePeriod | None = None
    due_date: str | None = None
    document_number: str | None = None
    pay_until: str | None = None
    total_amount: Decimal | None = None


class LegacyDarfRevenue(LegacyDarfModel):
    revenue_code: str | None = None
    reference_number: str | None = None
    principal_amount: Decimal | None = None
    penalty_amount: Decimal | None = None
    interest_amount: Decimal | None = None
    total_amount: Decimal | None = None


class LegacyDarfValidation(LegacyDarfModel):
    calculated_total_amount: Decimal | None = None
    sum_matches_total: bool | None = None


class LegacyDarfDocument(LegacyDarfModel):
    header: LegacyDarfHeader
    revenue: LegacyDarfRevenue
    validation: LegacyDarfValidation
    observation_reference: str | None = None
    observation_installment_number: int | None = None
    warning_codes: tuple[str, ...] = ()


class LocatedLegacyDarf(LegacyDarfModel):
    page_number: int
    block_number: int
    document: LegacyDarfDocument


class LegacyDarfFormExtraction(LegacyDarfModel):
    documents: tuple[LocatedLegacyDarf, ...]


def has_legacy_darf_form_layout(text: str) -> bool:
    normalized = search_text(text)
    title = "DOCUMENTO DE ARRECADACAO DE RECEITAS FEDERAIS" in normalized or (
        "MINISTERIO DA FAZENDA" in normalized and re.search(r"\bDARF\b", normalized)
    )
    numbered_fields = sum(
        marker in normalized
        for marker in (
            "PERIODO DE APURACAO",
            "CODIGO DA RECEITA",
            "DATA DE VENCIMENTO",
            "VALOR DO PRINCIPAL",
            "VALOR DOS JUROS",
            "VALOR TOTAL",
        )
    )
    modern_table = "COMPOSICAO DO DOCUMENTO DE ARRECADACAO" in normalized
    return bool(title and numbered_fields >= 5 and not modern_table)


class LegacyDarfFormExtractor:
    layout_id = LEGACY_DARF_FORM_LAYOUT_ID

    def supports_layout(self, context: DocumentContext) -> bool:
        if context.technical_format is not TechnicalFormat.PDF:
            return False
        pages = read_pdf_pages(context.file_path)
        return pages.status is ExtractionStatus.MATCHED and any(
            has_legacy_darf_form_layout(page) for page in pages.pages
        )

    def extract(self, context: DocumentContext) -> LegacyDarfFormExtraction:
        if context.technical_format is not TechnicalFormat.PDF:
            raise LayoutExtractionFailure(ExtractionStatus.UNSUPPORTED, "LAYOUT_FORMAT_UNSUPPORTED")
        pages = read_pdf_pages(context.file_path)
        if pages.status is ExtractionStatus.INVALID:
            raise LayoutExtractionFailure(ExtractionStatus.INVALID, "INVALID_PDF")
        if pages.status is ExtractionStatus.INCONCLUSIVE:
            raise LayoutExtractionFailure(ExtractionStatus.INCONCLUSIVE, "PDF_TEXT_LAYER_MISSING")

        located: list[LocatedLegacyDarf] = []
        seen: set[tuple[object, ...]] = set()
        for page_number, page in enumerate(pages.pages, start=1):
            for block_number, block in enumerate(legacy_darf_form_blocks(page), start=1):
                document = extract_legacy_darf_form(block)
                identity = (
                    document.header.taxpayer_id,
                    document.header.assessment_period.model_dump_json()
                    if document.header.assessment_period
                    else None,
                    document.header.due_date,
                    document.header.document_number,
                    document.revenue.revenue_code,
                    document.revenue.reference_number,
                    document.revenue.total_amount,
                )
                if identity in seen:
                    continue
                seen.add(identity)
                located.append(
                    LocatedLegacyDarf(
                        page_number=page_number,
                        block_number=block_number,
                        document=document,
                    )
                )
        if not located:
            raise LayoutExtractionFailure(ExtractionStatus.UNSUPPORTED, "UNKNOWN_GUIDE_LAYOUT")
        return LegacyDarfFormExtraction(documents=tuple(located))


def legacy_darf_form_blocks(text: str) -> tuple[str, ...]:
    """Split repeated receipt copies while retaining one-copy documents."""
    lines = text.splitlines()
    starts = [
        index
        for index, line in enumerate(lines)
        if re.search(r"\bDARF\b", search_text(line))
        and any(marker in search_text("\n".join(lines[index : index + 10])) for marker in ("PERIODO DE APURACAO", "CODIGO DA RECEITA"))
    ]
    if not starts:
        return (text,) if has_legacy_darf_form_layout(text) else ()
    blocks = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = "\n".join(lines[start:end])
        if has_legacy_darf_form_layout(block):
            blocks.append(block)
    return tuple(blocks)


def extract_legacy_darf_form(text: str) -> LegacyDarfDocument:
    if not has_legacy_darf_form_layout(text):
        raise ValueError("DARF_LEGACY_FORM_LAYOUT_REQUIRED")
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    warnings: list[str] = []

    taxpayer_value = _field_value(lines, "NUMERO DO CPF OU CNPJ", "NUMERO DO CPF/CNPJ") or ""
    cnpj = CNPJ_RE.search(taxpayer_value)
    cpf = CPF_RE.search(taxpayer_value)
    taxpayer_id = digits(cnpj[0]) if cnpj else digits(cpf[0]) if cpf else None
    taxpayer_kind = "CNPJ" if cnpj else "CPF" if cpf else None
    taxpayer_valid = valid_cnpj(taxpayer_id) if cnpj else valid_cpf(taxpayer_id) if cpf else None

    period = parse_guide_period(_field_value(lines, "PERIODO DE APURACAO"))
    due_date = parse_date(_field_value(lines, "DATA DE VENCIMENTO") or "")
    pay_until = parse_date(_field_value(lines, "DATA LIMITE PARA ACOLHIMENTO") or "")
    revenue_code = _digits_field(_field_value(lines, "CODIGO DA RECEITA"), minimum=4)
    reference_number = _digits_field(_field_value(lines, "NUMERO DE REFERENCIA"), minimum=4)
    principal = _money_field(lines, "VALOR DO PRINCIPAL")
    penalty = _money_field(lines, "VALOR DA MULTA") or Decimal("0.00")
    interest = _money_field(lines, "VALOR DOS JUROS") or Decimal("0.00")
    total = _money_field(lines, "VALOR TOTAL")
    calculated = principal + penalty + interest if principal is not None else None
    matches = abs(calculated - total) <= Decimal("0.01") if calculated is not None and total is not None else None

    for name, value in (
        ("TAXPAYER_ID", taxpayer_id),
        ("ASSESSMENT_PERIOD", period),
        ("DUE_DATE", due_date),
        ("PAY_UNTIL", pay_until),
        ("REVENUE_CODE", revenue_code),
        ("PRINCIPAL_AMOUNT", principal),
        ("TOTAL_AMOUNT", total),
    ):
        if value is None:
            warnings.append(f"{name}_MISSING")
    if taxpayer_valid is False:
        warnings.append("TAXPAYER_ID_INVALID_STRUCTURE")
    if matches is False:
        warnings.append("REVENUE_TOTAL_MISMATCH")

    observation_reference, observation_installment = _observation_identifiers(lines)
    header = LegacyDarfHeader(
        taxpayer_id=taxpayer_id,
        taxpayer_id_kind=taxpayer_kind,
        taxpayer_id_structure_valid=taxpayer_valid,
        taxpayer_name=_field_value(lines, "NOME / TELEFONE", "NOME/TELEFONE", "NOME / RAZAO SOCIAL", "NOME/RAZAO SOCIAL"),
        assessment_period=period,
        due_date=due_date,
        document_number=reference_number,
        pay_until=pay_until,
        total_amount=total,
    )
    return LegacyDarfDocument(
        header=header,
        revenue=LegacyDarfRevenue(
            revenue_code=revenue_code,
            reference_number=reference_number,
            principal_amount=principal,
            penalty_amount=penalty,
            interest_amount=interest,
            total_amount=total,
        ),
        validation=LegacyDarfValidation(
            calculated_total_amount=calculated,
            sum_matches_total=matches,
        ),
        observation_reference=observation_reference,
        observation_installment_number=observation_installment,
        warning_codes=tuple(dict.fromkeys(warnings)),
    )


def _field_value(lines: list[str], *labels: str) -> str | None:
    for label in labels:
        for index, line in enumerate(lines):
            normalized = unidecode(line).upper()
            found = re.search(rf"(?<![A-Z])(?:\d{{2}}\s*)?{re.escape(label)}(?![A-Z])", normalized)
            if not found:
                continue
            value_start = normalized.find(label, found.start())
            following = [
                match.start()
                for other in _FIELD_LABELS
                for match in (re.search(rf"(?<![A-Z])(?:\d{{2}}\s*)?{re.escape(other)}(?![A-Z])", normalized[found.end() :]),)
                if other != label and match
            ]
            # Classic DARF copies use two stable physical columns.  A label can
            # be alone on its row while the following value row also contains
            # the other column, so the page midpoint remains the cell boundary.
            end = found.end() + min(following) if following else (84 if value_start < 84 else len(line))
            candidate_end = end if following or value_start < 84 else None
            inline = line[found.end() : end].strip(" :-")
            label_suffix = label == "VALOR DOS JUROS" and MONEY_RE.search(inline) is None
            if inline and not label_suffix:
                return " ".join(inline.split())
            if index + 1 < len(lines):
                candidate = lines[index + 1][value_start:candidate_end].strip(" :-")
                if candidate and not any(other in search_text(candidate) for other in _FIELD_LABELS):
                    return " ".join(candidate.split())
    return None


def _money_field(lines: list[str], label: str) -> Decimal | None:
    value = _field_value(lines, label)
    match = MONEY_RE.search(value or "")
    return parse_money(match[0]) if match else None


def _digits_field(value: str | None, *, minimum: int) -> str | None:
    match = re.search(rf"(?<!\d)\d{{{minimum},30}}(?!\d)", digits(value or ""))
    return match[0] if match else None


def _observation_identifiers(lines: list[str]) -> tuple[str | None, int | None]:
    """Read only the two numeric observation cells of the classic SIEF parcel form."""
    for index, line in enumerate(lines):
        normalized = search_text(line)
        if "DATA LIMITE PARA ACOLHIMENTO" not in normalized:
            continue
        left_column = [candidate[:84].strip() for candidate in lines[index + 1 : index + 8]]
        numeric = [digits(candidate) for candidate in left_column if re.fullmatch(r"[\d.\-/ ]+", candidate)]
        reference = next((value for value in numeric if len(value) >= 12), None)
        installment = next((int(value) for value in numeric if value and len(value) <= 3), None)
        return reference, installment
    return None, None
