"""Federal/SENDA layout extraction, deliberately independent of guide family."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
import re

from pydantic import BaseModel, ConfigDict, Field
from unidecode import unidecode

from agent.parsers.guide_common import (
    CNPJ_RE, CPF_RE, MONEY_RE, digits, parse_date, parse_money,
    search_text, valid_cnpj, valid_cpf,
)

COMPOSITION_LABEL = "COMPOSICAO DO DOCUMENTO DE ARRECADACAO"
_LABELS = (
    "CNPJ/CPF", "CNPJ", "CPF", "RAZAO SOCIAL", "NOME", "PERIODO DE APURACAO",
    "DATA DE VENCIMENTO", "NUMERO DO DOCUMENTO", "PAGAR ESTE DOCUMENTO ATE",
    "VALOR TOTAL DO DOCUMENTO", "OBSERVACOES",
)
_MONTHS = dict(zip(
    ("JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO",
     "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"), range(1, 13), strict=True,
))
_ROW_RE = re.compile(r"^\s*(?P<code>\d{4})(?:-(?P<extension>\d{2}))?\s+(?P<description>.*\S)")
_DOC_NUMBER_RE = re.compile(r"(?<!\d)\d{2}\.\d{2}\.\d{5}\.\d{7}-\d(?!\d)")


def has_federal_revenue_form_layout(text: str) -> bool:
    """Recognize the federal revenue form independently of guide semantics."""
    normalized = search_text(text)
    title = "DOCUMENTO DE ARRECADACAO DE RECEITAS FEDERAIS" in normalized
    table = COMPOSITION_LABEL in normalized and all(
        label in normalized
        for label in ("CODIGO", "DENOMINACAO", "PRINCIPAL", "MULTA", "JUROS", "TOTAL")
    )
    markers = sum(
        label in normalized
        for label in (
            "PERIODO DE APURACAO",
            "DATA DE VENCIMENTO",
            "NUMERO DO DOCUMENTO",
            "PAGAR ESTE DOCUMENTO ATE",
            "VALOR TOTAL DO DOCUMENTO",
        )
    )
    return title and table and markers >= 2 and "SIMPLES NACIONAL" not in normalized


class PeriodKind(str, Enum):
    MONTH = "MONTH"
    QUARTER = "QUARTER"
    DATE = "DATE"
    RANGE = "RANGE"
    UNKNOWN = "UNKNOWN"


class GuidePeriod(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    label: str
    kind: PeriodKind
    month: str | None = None
    year: int | None = None
    quarter: int | None = None
    period_start: str | None = None
    period_end: str | None = None


class FederalGuideHeader(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    taxpayer_id: str | None = None
    taxpayer_id_kind: str | None = None
    taxpayer_id_structure_valid: bool | None = None
    taxpayer_name: str | None = None
    assessment_period: GuidePeriod | None = None
    observed_header_period: GuidePeriod | None = None
    assessment_period_source: str | None = None
    due_date: str | None = None
    document_number: str | None = None
    pay_until: str | None = None
    total_amount: Decimal | None = None
    declaration_receipt_number: str | None = None


class FederalRevenue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    revenue_code: str
    code_extension: str | None = None
    description: str
    tax: str = "UNKNOWN"
    tax_identification_source: str | None = None
    detail_description: str | None = None
    assessment_period: GuidePeriod | None = None
    due_date: str | None = None
    principal_amount: Decimal | None = None
    penalty_amount: Decimal | None = None
    interest_amount: Decimal | None = None
    total_amount: Decimal | None = None


class FederalGuideValidation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    revenues_total_amount: Decimal | None = None
    sum_matches_total: bool | None = None
    pay_until_matches_due_date: bool | None = None


class FederalRevenueGuide(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    header: FederalGuideHeader
    revenues: tuple[FederalRevenue, ...]
    validation: FederalGuideValidation
    warning_codes: tuple[str, ...] = Field(default_factory=tuple)


def parse_guide_period(label: str | None) -> GuidePeriod | None:
    if not label or not label.strip():
        return None
    label = " ".join(label.strip(" :").split())
    normalized = search_text(label)
    quarter = re.fullmatch(r"([1-4])(?:[O°º.]|\s)*\s*TRIMESTRE\s*[/ -]?\s*(\d{4})", normalized)
    if quarter:
        return GuidePeriod(label=label, kind=PeriodKind.QUARTER, quarter=int(quarter[1]), year=int(quarter[2]))
    month = re.fullmatch(r"(0?[1-9]|1[0-2])[/ -](\d{4})", normalized)
    named = re.fullmatch(r"([A-Z]+)\s*[/ -]\s*(\d{4})", normalized)
    if month or (named and named[1] in _MONTHS):
        year = int(month[2] if month else named[2])
        number = int(month[1]) if month else _MONTHS[named[1]]
        return GuidePeriod(label=label, kind=PeriodKind.MONTH, month=f"{year:04d}-{number:02d}", year=year)
    exact_date = parse_date(label)
    if exact_date:
        return GuidePeriod(label=label, kind=PeriodKind.DATE, period_start=exact_date, period_end=exact_date)
    interval = re.fullmatch(r"(\d{2}/\d{2}/\d{4})\s*(?:A|ATE|-)\s*(\d{2}/\d{2}/\d{4})", normalized)
    if interval:
        start, end = parse_date(interval[1]), parse_date(interval[2])
        if start and end and start <= end:
            return GuidePeriod(label=label, kind=PeriodKind.RANGE, period_start=start, period_end=end)
    return GuidePeriod(label=label, kind=PeriodKind.UNKNOWN)


def _label_value(lines: list[str], label: str) -> str | None:
    """Read inline fields or actual SENDA label/value columns without cross-field search."""
    for index, line in enumerate(lines):
        # Preserve spacing: compact normalization would destroy column positions.
        normalized = unidecode(line).upper()
        found = re.search(rf"(?<![A-Z]){re.escape(label)}(?![A-Z])", normalized)
        if not found:
            continue
        following_labels = [normalized.find(other, found.end()) for other in _LABELS if other != label]
        following = min((position for position in following_labels if position >= 0), default=len(line))
        remainder = line[found.end():following].strip(" :")
        if remainder:
            return remainder
        column_end = following if following < len(line) else None
        # The PA cell can intentionally be empty. Never scan later rows for it:
        # an unrelated payment date can occupy the same horizontal coordinates.
        row_count = 2 if label == "PAGAR ESTE DOCUMENTO ATE" else 1
        for candidate in lines[index + 1:index + 1 + row_count]:
            cell = candidate[found.start():column_end].strip(" :")
            if cell and not any(other in search_text(cell) for other in _LABELS):
                return cell
    return None


class FederalRevenueGuideExtractor:
    """Extract header/table/validation even from an excluded installment shell.

    Does not select family or touch filesystem, registry, backend or canonical fields.
    Tax identification is supplied by the consumer, not encoded in layout regexes.
    """

    def extract(self, text: str) -> FederalRevenueGuide:
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        composition = next((i for i, line in enumerate(lines) if COMPOSITION_LABEL in search_text(line)), len(lines))
        header_lines = lines[:composition]
        header_text = "\n".join(header_lines)
        taxpayer_cell = (_label_value(header_lines, "CNPJ/CPF") or _label_value(header_lines, "CNPJ")
                         or _label_value(header_lines, "CPF") or "")
        # A declaration receipt can also have 14 digits. Only a taxpayer-labelled
        # cell is authority for taxpayer identity, never an arbitrary header token.
        cnpj = CNPJ_RE.search(taxpayer_cell)
        cpf = CPF_RE.search(taxpayer_cell)
        identifier = digits(cnpj[0]) if cnpj else digits(cpf[0]) if cpf else None
        kind = "CNPJ" if cnpj else "CPF" if cpf else None
        valid = valid_cnpj(identifier) if cnpj else valid_cpf(identifier) if cpf else None
        warnings: list[str] = []
        revenues = self._revenues(lines[composition + 1:], warnings)
        header_period = parse_guide_period(_label_value(header_lines, "PERIODO DE APURACAO"))
        observed_header_period = header_period
        period_source = "HEADER" if header_period else None
        periods = [row.assessment_period for row in revenues if row.assessment_period]
        semantics = {_period_key(period) for period in periods}
        if periods and len(semantics) == 1 and len(periods) == len(revenues):
            if header_period is None or _period_key(header_period) != _period_key(periods[0]):
                if header_period:
                    warnings.append("ASSESSMENT_PERIOD_HEADER_DIFFERS_FROM_REVENUES")
                header_period, period_source = periods[0], "REVENUES_CONSENSUS"
        elif len(semantics) > 1:
            warnings.append("ASSESSMENT_PERIOD_MULTIPLE")
        number = _label_value(header_lines, "NUMERO DO DOCUMENTO")
        number_match = _DOC_NUMBER_RE.fullmatch(number or "")
        total = _label_value(header_lines, "VALOR TOTAL DO DOCUMENTO")
        total_match = MONEY_RE.fullmatch(total or "")
        receipt = re.search(r"(?:N[O°º]?\s*)?RECIBO\s+DECLARA[CÇ][AÃ]O\s*:\s*(\d{1,30})(?!\d)", header_text, re.I)
        header = FederalGuideHeader(
            taxpayer_id=identifier, taxpayer_id_kind=kind, taxpayer_id_structure_valid=valid,
            taxpayer_name=_label_value(header_lines, "RAZAO SOCIAL") or _label_value(header_lines, "NOME"),
            assessment_period=header_period, assessment_period_source=period_source,
            observed_header_period=observed_header_period,
            due_date=parse_date(_label_value(header_lines, "DATA DE VENCIMENTO") or ""),
            document_number=number_match[0] if number_match else None,
            pay_until=parse_date(_label_value(header_lines, "PAGAR ESTE DOCUMENTO ATE") or ""),
            total_amount=parse_money(total_match[0]) if total_match else None,
            declaration_receipt_number=receipt[1] if receipt else None,
        )
        for name in ("taxpayer_id", "taxpayer_name", "assessment_period", "due_date", "document_number", "pay_until", "total_amount"):
            if getattr(header, name) is None:
                warnings.append(f"{name.upper()}_MISSING")
        if valid is False:
            warnings.append("TAXPAYER_ID_INVALID_STRUCTURE")
        if header_period and header_period.kind is PeriodKind.UNKNOWN:
            warnings.append("ASSESSMENT_PERIOD_UNPARSED")
        validation = validate_totals(header, revenues)
        if validation.sum_matches_total is False:
            warnings.append("REVENUE_TOTAL_MISMATCH")
        if validation.pay_until_matches_due_date is False:
            warnings.append("PAY_UNTIL_DIFFERS_FROM_DUE_DATE")
        return FederalRevenueGuide(header=header, revenues=revenues, validation=validation,
                                   warning_codes=tuple(dict.fromkeys(warnings)))

    def _revenues(self, lines: list[str], warnings: list[str]) -> tuple[FederalRevenue, ...]:
        end = next((i for i, line in enumerate(lines)
                    if search_text(line).startswith(("TOTAIS", "SENDA", "AUTENTICACAO", "DOCUMENTO DE ARRECADACAO"))), len(lines))
        lines = lines[:end]
        columns = None
        for line in lines:
            normalized_line = unidecode(line).upper()
            labels = [re.search(rf"\b{label}\b", normalized_line) for label in ("PRINCIPAL", "MULTA", "JUROS", "TOTAL")]
            if all(labels) and re.search(r"\S\s{2,}\S", line):
                centers = [(label.start() + label.end()) / 2 for label in labels]
                if all(right - left >= 8 for left, right in zip(centers, centers[1:])):
                    columns = centers
                    break
        starts = [(i, match) for i, line in enumerate(lines) if (match := _ROW_RE.match(line))]
        rows: list[FederalRevenue] = []
        for position, (index, match) in enumerate(starts):
            next_index = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
            group = lines[index:next_index]
            description = MONEY_RE.split(match["description"])[0].strip(" -|")
            normalized = search_text(" ".join(group[1:]))
            pa = re.search(r"\bPA\s*:?[ ]*(.+?)(?=\s+VENCIMENTO\b|$)", normalized)
            period = parse_guide_period(pa[1]) if pa else None
            due = re.search(r"\bVENCIMENTO\s*:?\s*(\d{2}/\d{2}/\d{4})", normalized)
            detail_line = next((re.match(r"^\s*(\d{2})\s+(.+)", line) for line in group[1:]
                                if re.match(r"^\s*\d{2}\s+[A-Z]", search_text(line))), None)
            extension = match["extension"] or (detail_line[1] if detail_line else None)
            detail = detail_line[2].strip() if detail_line else None
            # Only the row's amount cells, never PA, identifiers or footer numbers.
            money_matches = list(MONEY_RE.finditer(group[0]))
            values = [parse_money(m[0]) for m in money_matches]
            amounts: list[Decimal | None] = [None, None, None, None]
            slots = [min(range(4), key=lambda i: abs((m.start() + m.end()) / 2 - columns[i]))
                     for m in money_matches] if columns else []
            if columns and len(slots) == len(set(slots)) and 0 in slots and 3 in slots:
                amounts = [Decimal("0.00")] * 4
                for slot, value in zip(slots, values, strict=True):
                    amounts[slot] = value
            elif len(values) == 4:
                amounts = values
            elif len(values) == 2:
                amounts = [values[0], Decimal("0.00"), Decimal("0.00"), values[1]]
            else:
                # Three cells are ambiguous (one blank surcharge): do not shift columns.
                warnings.append("REVENUE_AMOUNTS_INCOMPLETE")
                if values:
                    amounts[0] = values[0]
                if len(values) > 1:
                    amounts[3] = values[-1]
            if not period:
                warnings.append("REVENUE_PERIOD_MISSING")
            elif period.kind is PeriodKind.UNKNOWN:
                warnings.append("REVENUE_PERIOD_UNPARSED")
            rows.append(FederalRevenue(
                revenue_code=(f'{match["code"]}-{match["extension"]}' if match["extension"] else match["code"]),
                code_extension=extension, description=description or "UNKNOWN",
                detail_description=detail, assessment_period=period, due_date=parse_date(due[1]) if due else None,
                principal_amount=amounts[0], penalty_amount=amounts[1], interest_amount=amounts[2], total_amount=amounts[3],
            ))
        if not rows:
            warnings.append("REVENUES_MISSING")
        return tuple(rows)


def _period_key(period: GuidePeriod) -> tuple:
    return (period.kind, period.month, period.year, period.quarter, period.period_start, period.period_end,
            period.label if period.kind is PeriodKind.UNKNOWN else None)


def validate_totals(header: FederalGuideHeader, revenues: tuple[FederalRevenue, ...]) -> FederalGuideValidation:
    complete = bool(revenues) and all(row.total_amount is not None for row in revenues)
    total = sum((row.total_amount for row in revenues if row.total_amount is not None), Decimal("0.00")) if complete else None
    return FederalGuideValidation(
        revenues_total_amount=total,
        sum_matches_total=(abs(total - header.total_amount) <= Decimal("0.01")
                           if total is not None and header.total_amount is not None else None),
        pay_until_matches_due_date=(header.pay_until == header.due_date
                                   if header.pay_until and header.due_date else None),
    )
