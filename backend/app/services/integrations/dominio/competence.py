from __future__ import annotations

from dataclasses import dataclass
import re


PAYROLL_COMPETENCE_RE = re.compile(r"^(0[1-9]|1[0-2])\/(\d{4})$")


@dataclass(frozen=True, slots=True)
class PayrollCompetenceMapping:
    source_payroll_competence: str
    target_assessment_competence: str

    @property
    def payroll_competence(self) -> str:
        return self.source_payroll_competence

    @property
    def assessment_competence(self) -> str:
        return self.target_assessment_competence


def normalize_payroll_competence(value: str) -> str:
    text = str(value).strip()
    match = PAYROLL_COMPETENCE_RE.fullmatch(text)
    if match is None:
        raise ValueError(
            "Payroll competence must use canonical MM/YYYY format with an unambiguous month and year."
        )
    month = int(match.group(1))
    year = int(match.group(2))
    if year < 1900 or year > 9999:
        raise ValueError("Payroll competence year must be between 1900 and 9999.")
    return f"{year:04d}-{month:02d}"


def map_payroll_to_assessment_competence(value: str) -> PayrollCompetenceMapping:
    payroll_competence = normalize_payroll_competence(value)
    year = int(payroll_competence[:4])
    month = int(payroll_competence[5:7])

    if month == 12:
        assessment_year = year + 1
        assessment_month = 1
    else:
        assessment_year = year
        assessment_month = month + 1

    return PayrollCompetenceMapping(
        source_payroll_competence=payroll_competence,
        target_assessment_competence=f"{assessment_year:04d}-{assessment_month:02d}",
    )
