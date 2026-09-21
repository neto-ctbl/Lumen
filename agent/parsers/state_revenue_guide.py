"""DARE-GO 5.1 structural extraction; deliberately does not classify guide kinds."""

from __future__ import annotations

from decimal import Decimal
import re

from pydantic import BaseModel, ConfigDict
from unidecode import unidecode

from agent.parsers.federal_revenue_guide import GuidePeriod, parse_guide_period
from agent.parsers.guide_common import (
    CNPJ_RE, CPF_RE, MONEY_RE, digits, parse_date, parse_money, search_text,
    valid_cnpj, valid_cpf,
)


class StateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StateGuideHeader(StateModel):
    layout: str = "DARE_GO_5_1"
    taxpayer_id: str | None = None
    taxpayer_id_kind: str | None = None
    taxpayer_id_structure_valid: bool | None = None
    state_registration: str | None = None
    taxpayer_name: str | None = None
    uf: str | None = None
    taxpayer_uf: str | None = None
    reference_label: str | None = None
    reference_frequency_code: str | None = None
    reference_period: GuidePeriod | None = None
    reference_period_source: str | None = None
    due_date: str | None = None
    pay_until: str | None = None
    document_number: str | None = None
    origin_document: str | None = None
    condition_code: str | None = None
    installment_reference: str | None = None
    total_amount: Decimal | None = None


class StateComponent(StateModel):
    code: str | None = None
    label: str
    kind: str
    amount: Decimal


class StateRevenue(StateModel):
    revenue_code: str
    description: str
    parent_revenue_code: str | None = None
    parent_description: str | None = None
    tax: str = "UNKNOWN"
    guide_kind: str = "UNKNOWN"
    classification_source: str | None = None
    components: tuple[StateComponent, ...] = ()
    principal_amount: Decimal | None = None
    penalty_amount: Decimal | None = None
    interest_amount: Decimal | None = None
    total_amount: Decimal | None = None


class StateGuideValidation(StateModel):
    components_total_amount: Decimal | None = None
    sum_matches_total: bool | None = None
    pay_until_matches_due_date: bool | None = None


class ExtractedStateGuide(StateModel):
    header: StateGuideHeader
    revenues: tuple[StateRevenue, ...]
    validation: StateGuideValidation
    warning_codes: tuple[str, ...] = ()


_LABELS = (
    "CONTRIBUINTE", "INSCRICAO ESTADUAL", "CNPJ/CPF", "CNPJ", "CPF",
    "ENDERECO", "MUNICIPIO", "UF", "DDD/TELEFONE", "DOCUMENTO DE ORIGEM",
    "DATA DE VENCIMENTO", "CONDICAO", "REFERENCIA", "PARCELA",
    "VALIDADE DO", "TOTAL A RECOLHER", "INFORMACOES COMPLEMENTARES", "DATA E HORA DE",
)
_ROW = re.compile(r"^\s*(\d{1,8})\s*-\s*(\S.*)")
_CHARGE = re.compile(r"\b(VALOR ORIGINAL|PRINCIPAL|MULTA(?: DE MORA)?|JUROS(?: DE MORA)?|ACRESCIMOS|OUTROS)\b")


def has_go_dare_51_layout(text: str) -> bool:
    """Recognize the Goiás DARE 5.1 shell without classifying its revenue."""
    normalized = search_text(text)
    return (
        "DOCUMENTO DE ARRECADACAO DE RECEITAS ESTADUAIS" in normalized
        and re.search(r"\bDARE\s+5\.1\b", normalized) is not None
        and "ESTADO DE GOIAS" in normalized
        and "SECRETARIA DA ECONOMIA" in normalized
        and all(label in normalized for label in ("RECEITA", "ALINEAS", "VALORES", "CONTRIBUINTE"))
        and sum(
            label in normalized
            for label in ("REFERENCIA", "DATA DE VENCIMENTO", "TOTAL A RECOLHER")
        )
        >= 2
    )


def field_value(lines: list[str], label: str) -> str | None:
    """Read an inline cell or the next physical row, never scan unrelated rows."""
    lines = [line for line in lines if line.strip()]
    for index, line in enumerate(lines):
        normalized = unidecode(line).upper()
        match = re.search(rf"(?<![A-Z]){re.escape(label)}(?![A-Z])", normalized)
        if not match:
            continue
        ends = [m.start() for other in _LABELS if other != label
                for m in re.finditer(rf"(?<![A-Z]){re.escape(other)}(?![A-Z])", normalized)
                if m.start() >= match.end()]
        end = min(ends, default=len(line))
        inline = line[match.end():end].strip(" :")
        if inline and inline != "-":
            return inline
        if inline == "-":
            return None
        if index + 1 < len(lines):
            # A single-column synthetic form has no right boundary; real DARE
            # columns retain their actual positions from pypdf layout extraction.
            cell = lines[index + 1][match.start():end if ends else None].strip(" :")
            if cell and cell != "-" and not any(other in search_text(cell) for other in _LABELS):
                return cell
    return None


def _amount_field(lines: list[str], label: str) -> Decimal | None:
    value = field_value(lines, label)
    match = MONEY_RE.fullmatch(value or "")
    return parse_money(match[0]) if match else None


def _sum_kind(components: tuple[StateComponent, ...], kind: str) -> Decimal | None:
    values = [component.amount for component in components if component.kind == kind]
    return sum(values, Decimal("0")) if values else None


class StateRevenueGuideExtractor:
    """Reusable structural shell, including guides subsequently excluded as installments."""

    def extract(self, text: str) -> ExtractedStateGuide:
        lines = [line for line in text.splitlines() if line.strip()]
        warnings: list[str] = []
        taxpayer = field_value(lines, "CNPJ/CPF") or field_value(lines, "CNPJ") or field_value(lines, "CPF")
        cnpj = CNPJ_RE.fullmatch(taxpayer or "")
        cpf = CPF_RE.fullmatch(taxpayer or "")
        identifier = digits(cnpj[0] if cnpj else cpf[0]) if cnpj or cpf else None
        valid = valid_cnpj(identifier) if cnpj else valid_cpf(identifier) if cpf else None
        if identifier is None:
            warnings.append("TAXPAYER_ID_MISSING")
        elif valid is False:
            warnings.append("TAXPAYER_ID_INVALID")
        reference = field_value(lines, "REFERENCIA")
        frequency = re.match(r"^(\d+)\s*-\s*[^-]+\s*-\s*(.+)$", reference or "")
        period = parse_guide_period(frequency[2] if frequency else reference)
        if period is None:
            warnings.append("REFERENCE_MISSING")
        elif period.kind == "UNKNOWN":
            warnings.append("REFERENCE_UNINTERPRETED")
        numbers = [m[1] for line in lines
                   if "DOCUMENTO DE ARRECADACAO DE RECEITAS ESTADUAIS" in search_text(line)
                   for m in re.finditer(r"\bN[O°º]?\s*[.:]?\s*(\d{5,30})\b", unidecode(line).upper())]
        number = numbers[0] if numbers else field_value(lines, "NUMERO DO DOCUMENTO")
        if number is None:
            warnings.append("DOCUMENT_NUMBER_MISSING")
        due_label = field_value(lines, "DATA DE VENCIMENTO")
        pay_label = field_value(lines, "VALIDADE DO")
        due = parse_date(due_label or "")
        pay = parse_date(pay_label or "")
        if not due:
            warnings.append("DUE_DATE_MISSING_OR_INVALID")
        if pay_label and not pay:
            warnings.append("PAY_UNTIL_INVALID")
        total = _amount_field(lines, "TOTAL A RECOLHER")
        if total is None:
            warnings.append("TOTAL_MISSING")
        taxpayer_uf = field_value(lines, "UF")
        header = StateGuideHeader(
            taxpayer_id=identifier, taxpayer_id_kind="CNPJ" if cnpj else "CPF" if cpf else None,
            taxpayer_id_structure_valid=valid,
            state_registration=field_value(lines, "INSCRICAO ESTADUAL"),
            taxpayer_name=field_value(lines, "CONTRIBUINTE"),
            uf="GO" if "ESTADO DE GOIAS" in search_text(text) else None,
            taxpayer_uf=taxpayer_uf if re.fullmatch(r"[A-Z]{2}", taxpayer_uf or "") else None,
            reference_label=reference, reference_frequency_code=frequency[1] if frequency else None,
            reference_period=period, reference_period_source="CONTENT_REFERENCE" if reference else None,
            due_date=due, pay_until=pay, document_number=number,
            origin_document=field_value(lines, "DOCUMENTO DE ORIGEM"),
            condition_code=field_value(lines, "CONDICAO"),
            installment_reference=field_value(lines, "PARCELA"), total_amount=total,
        )
        revenues = self._revenues(lines, warnings)
        if not revenues:
            warnings.append("REVENUES_MISSING")
        components = [component for row in revenues for component in row.components]
        component_total = sum((c.amount for c in components), Decimal("0")) if components else None
        matches = component_total == total if component_total is not None and total is not None else None
        if matches is False:
            warnings.append("COMPONENT_TOTAL_MISMATCH")
        return ExtractedStateGuide(
            header=header, revenues=revenues,
            validation=StateGuideValidation(
                components_total_amount=component_total, sum_matches_total=matches,
                pay_until_matches_due_date=pay == due if pay and due else None,
            ), warning_codes=tuple(dict.fromkeys(warnings)),
        )

    def _revenues(self, lines: list[str], warnings: list[str]) -> tuple[StateRevenue, ...]:
        start = next((i for i, line in enumerate(lines)
                      if re.match(r"^\s*RECEITA\b", unidecode(line).upper())), None)
        if start is None:
            return ()
        normalized = unidecode(lines[start]).upper()
        boundary = normalized.find("ALINEAS")
        end = next((i for i in range(start + 1, len(lines))
                    if any(label in search_text(lines[i]) for label in (
                        "DOCUMENTO DE ORIGEM", "REFERENCIA", "DATA DE VENCIMENTO",
                        "INFORMACOES COMPLEMENTARES", "VALIDADE DO", "TOTAL A RECOLHER",
                    ))), len(lines))
        rows: list[StateRevenue] = []
        current_code: str | None = None
        descriptions: list[str] = []
        parent_code: str | None = None
        parent_description: str | None = None
        components: list[StateComponent] = []

        def flush() -> None:
            if current_code is None:
                return
            items = tuple(components)
            rows.append(StateRevenue(
                revenue_code=current_code, description=" ".join(descriptions),
                parent_revenue_code=parent_code, parent_description=parent_description,
                components=items, principal_amount=_sum_kind(items, "PRINCIPAL"),
                penalty_amount=_sum_kind(items, "PENALTY"), interest_amount=_sum_kind(items, "INTEREST"),
                total_amount=sum((c.amount for c in items), Decimal("0")) if items else None,
            ))

        for line in lines[start + 1:end]:
            area = line[boundary:] if boundary >= 0 else line
            norm = unidecode(area).upper()
            charge = _CHARGE.search(norm)
            left = line[:boundary] if boundary >= 0 else line[:charge.start()] if charge else line
            row = _ROW.match(left)
            if row:
                code, description = row.groups()
                if current_code in ("1", "4014") and parent_code is None:
                    parent_code, parent_description = current_code, " ".join(descriptions)
                    current_code, descriptions = code, [description.strip()]
                else:
                    flush()
                    current_code, descriptions = code, [description.strip()]
                    parent_code, parent_description, components = None, None, []
            elif left.strip() and current_code:
                descriptions.append(left.strip())
            charges = list(_CHARGE.finditer(norm))
            for index, observed in enumerate(charges):
                stop = charges[index + 1].start() if index + 1 < len(charges) else len(area)
                value = area[observed.end():stop]
                money = list(MONEY_RE.finditer(value))
                if len(money) == 1:
                    code_match = re.search(r"\((\d+)\)", value)
                    label = area[observed.start():observed.end()]
                    kind = {"VALOR ORIGINAL": "PRINCIPAL", "PRINCIPAL": "PRINCIPAL"}.get(observed[1])
                    kind = kind or ("PENALTY" if observed[1].startswith("MULTA") else
                                    "INTEREST" if observed[1].startswith("JUROS") else "UNKNOWN")
                    components.append(StateComponent(code=code_match[1] if code_match else None,
                                                     label=label, kind=kind, amount=parse_money(money[0][0])))
                    if kind == "UNKNOWN":
                        warnings.append("COMPONENT_KIND_UNKNOWN")
                else:
                    warnings.append("COMPONENT_AMOUNT_MISSING_OR_AMBIGUOUS")
        flush()
        return tuple(rows)
