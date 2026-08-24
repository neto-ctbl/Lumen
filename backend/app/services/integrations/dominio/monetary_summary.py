from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from backend.app.services.integrations.dominio.contracts import (
    DominioPayrollCompany,
    DominioPayrollSectionType,
    DominioPayrollWarning,
    DominioPayrollWarningCode,
    DominioPayrollRubric,
)
from backend.app.services.integrations.dominio.normalization import normalize_search_text


DOMINIO_PAYROLL_RUBRICS_SCHEMA_VERSION = 2
MONETARY_QUANTUM = Decimal("0.01")
ZERO = Decimal("0.00")
MONETARY_SUMMARY_COMPLETE = "COMPLETE"
MONETARY_SUMMARY_PARTIAL = "PARTIAL"
MONETARY_SUMMARY_INSUFFICIENT = "INSUFFICIENT"
MONETARY_CONFIDENCE_HIGH = "HIGH"
MONETARY_CONFIDENCE_MEDIUM = "MEDIUM"

EMPLOYEE_REMUNERATION = "employee_remuneration"
PRO_LABORE = "pro_labore"
AUTONOMOUS = "autonomous"
THIRTEENTH_SALARY = "thirteenth_salary"
EMPLOYER_CPP_OBSERVED = "employer_cpp_observed"
FGTS_OBSERVED = "fgts_observed"
EXCLUDED = "excluded"

CATEGORY_ORDER = (
    EMPLOYEE_REMUNERATION,
    PRO_LABORE,
    AUTONOMOUS,
    THIRTEENTH_SALARY,
    EMPLOYER_CPP_OBSERVED,
    FGTS_OBSERVED,
)


@dataclass(frozen=True, slots=True)
class MonetaryRule:
    category: str
    confidence: str
    allowed_sections: frozenset[DominioPayrollSectionType] | None = None
    required_terms: tuple[str, ...] = ()
    forbidden_terms: tuple[str, ...] = ()

    def matches(self, rubric: DominioPayrollRubric) -> bool:
        if self.allowed_sections is not None and rubric.section not in self.allowed_sections:
            return False
        normalized_name = normalize_search_text(rubric.original_name)
        if self.required_terms and not all(term in normalized_name for term in self.required_terms):
            return False
        if self.forbidden_terms and any(term in normalized_name for term in self.forbidden_terms):
            return False
        return True


@dataclass(slots=True)
class MonetaryBucket:
    amount: Decimal = ZERO
    rubric_count: int = 0
    rubric_codes: set[str] | None = None

    def __post_init__(self) -> None:
        if self.rubric_codes is None:
            self.rubric_codes = set()

    def add(self, rubric: DominioPayrollRubric) -> None:
        assert self.rubric_codes is not None
        amount = rubric.calculated_value or ZERO
        self.amount = (self.amount + amount).quantize(MONETARY_QUANTUM)
        self.rubric_count += 1
        if rubric.code:
            self.rubric_codes.add(rubric.code)

    def to_payload(self, *, confidence: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "amount": _decimal_to_string(self.amount),
            "rubric_count": self.rubric_count,
            "rubric_codes": sorted(self.rubric_codes or ()),
        }
        if confidence is not None:
            payload["classification_confidence"] = confidence
        return payload


RUBRIC_MONETARY_CLASSIFICATION: dict[str, tuple[MonetaryRule, ...]] = {
    "1": (
        MonetaryRule(
            category=EMPLOYEE_REMUNERATION,
            confidence=MONETARY_CONFIDENCE_HIGH,
            allowed_sections=frozenset({DominioPayrollSectionType.EARNINGS}),
            required_terms=("horas", "normais"),
        ),
    ),
    "13": (
        MonetaryRule(
            category=THIRTEENTH_SALARY,
            confidence=MONETARY_CONFIDENCE_HIGH,
            allowed_sections=frozenset({DominioPayrollSectionType.EARNINGS}),
            required_terms=("13", "salario"),
        ),
    ),
    "19": (
        MonetaryRule(
            category=EMPLOYEE_REMUNERATION,
            confidence=MONETARY_CONFIDENCE_HIGH,
            allowed_sections=frozenset({DominioPayrollSectionType.EARNINGS}),
            required_terms=("diferenca", "salarios"),
        ),
    ),
    "23": (
        MonetaryRule(
            category=FGTS_OBSERVED,
            confidence=MONETARY_CONFIDENCE_MEDIUM,
            allowed_sections=frozenset({DominioPayrollSectionType.INFORMATIONAL}),
            required_terms=("f g t s",),
        ),
    ),
    "100": (
        MonetaryRule(
            category=PRO_LABORE,
            confidence=MONETARY_CONFIDENCE_HIGH,
            allowed_sections=frozenset({DominioPayrollSectionType.EARNINGS}),
            required_terms=("pro", "labore"),
        ),
    ),
    "235": (
        MonetaryRule(
            category=AUTONOMOUS,
            confidence=MONETARY_CONFIDENCE_HIGH,
            allowed_sections=frozenset({DominioPayrollSectionType.EARNINGS}),
            required_terms=("autonomo",),
        ),
    ),
    "843": (
        MonetaryRule(
            category=EMPLOYER_CPP_OBSERVED,
            confidence=MONETARY_CONFIDENCE_MEDIUM,
            allowed_sections=frozenset({DominioPayrollSectionType.DEDUCTIONS}),
            required_terms=("inss", "empregador"),
        ),
    ),
    "858": (
        MonetaryRule(
            category=EXCLUDED,
            confidence=MONETARY_CONFIDENCE_HIGH,
            allowed_sections=frozenset({DominioPayrollSectionType.DEDUCTIONS}),
            required_terms=(),
        ),
    ),
    "996": (
        MonetaryRule(
            category=FGTS_OBSERVED,
            confidence=MONETARY_CONFIDENCE_MEDIUM,
            allowed_sections=frozenset({DominioPayrollSectionType.INFORMATIONAL}),
            required_terms=("f g t s",),
        ),
    ),
    "998": (
        MonetaryRule(
            category=EXCLUDED,
            confidence=MONETARY_CONFIDENCE_HIGH,
            allowed_sections=frozenset({DominioPayrollSectionType.DEDUCTIONS}),
            required_terms=(),
            forbidden_terms=("empregador",),
        ),
    ),
}


def build_dominio_monetary_summary(company: DominioPayrollCompany) -> tuple[dict[str, Any], list[DominioPayrollWarning]]:
    buckets = {category: MonetaryBucket() for category in CATEGORY_ORDER}
    unclassified = MonetaryBucket()
    excluded = MonetaryBucket()

    relevant_count = 0
    for rubric in company.rubrics:
        if rubric.calculated_value is None:
            continue
        relevant_count += 1
        category = classify_monetary_rubric(rubric)
        if category is None:
            unclassified.add(rubric)
            continue
        if category == EXCLUDED:
            excluded.add(rubric)
            continue
        buckets[category].add(rubric)

    coverage = _resolve_coverage(
        relevant_count=relevant_count,
        classified_count=sum(bucket.rubric_count for bucket in buckets.values()),
        unclassified_count=unclassified.rubric_count,
    )

    payload = {
        "schema_version": DOMINIO_PAYROLL_RUBRICS_SCHEMA_VERSION,
        "monetary_summary_confidence": coverage,
        "monetary_categories": {
            EMPLOYEE_REMUNERATION: buckets[EMPLOYEE_REMUNERATION].to_payload(confidence=MONETARY_CONFIDENCE_HIGH),
            PRO_LABORE: buckets[PRO_LABORE].to_payload(confidence=MONETARY_CONFIDENCE_HIGH),
            AUTONOMOUS: buckets[AUTONOMOUS].to_payload(confidence=MONETARY_CONFIDENCE_HIGH),
            THIRTEENTH_SALARY: buckets[THIRTEENTH_SALARY].to_payload(confidence=MONETARY_CONFIDENCE_HIGH),
            EMPLOYER_CPP_OBSERVED: buckets[EMPLOYER_CPP_OBSERVED].to_payload(confidence=MONETARY_CONFIDENCE_MEDIUM),
            FGTS_OBSERVED: buckets[FGTS_OBSERVED].to_payload(confidence=MONETARY_CONFIDENCE_MEDIUM),
        },
        "unclassified_monetary": unclassified.to_payload(),
        "excluded_monetary": excluded.to_payload(confidence=MONETARY_CONFIDENCE_HIGH),
    }

    warnings: list[DominioPayrollWarning] = []
    if unclassified.rubric_count:
        warnings.append(
            DominioPayrollWarning(
                code=DominioPayrollWarningCode.UNCLASSIFIED_MONETARY_RUBRICS,
                message="The payroll movement contains monetary rubrics that could not be classified conservatively.",
                company_key=company.company_key,
                context={
                    "unclassified_amount": _decimal_to_string(unclassified.amount),
                    "rubric_count": unclassified.rubric_count,
                    "rubric_codes": sorted(unclassified.rubric_codes or ()),
                },
            )
        )

    return payload, warnings


def classify_monetary_rubric(rubric: DominioPayrollRubric) -> str | None:
    rules = RUBRIC_MONETARY_CLASSIFICATION.get(rubric.code, ())
    for rule in rules:
        if rule.matches(rubric):
            return rule.category
    return None


def merge_rubrics_summary(company: DominioPayrollCompany, *, base_summary: dict[str, Any]) -> tuple[dict[str, Any], list[DominioPayrollWarning]]:
    monetary_summary, warnings = build_dominio_monetary_summary(company)
    merged = dict(base_summary)
    merged.update(monetary_summary)
    return merged, warnings


def _resolve_coverage(*, relevant_count: int, classified_count: int, unclassified_count: int) -> str:
    if relevant_count == 0 or classified_count == 0:
        return MONETARY_SUMMARY_INSUFFICIENT
    if unclassified_count:
        return MONETARY_SUMMARY_PARTIAL
    return MONETARY_SUMMARY_COMPLETE


def _decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.quantize(MONETARY_QUANTUM), "f")
