from __future__ import annotations

from dataclasses import dataclass
import re

from backend.app.services.integrations.dominio.normalization import normalize_search_text


PRO_LABORE_CODES = frozenset({"100", "9380"})
AUTONOMOUS_CODES = frozenset({"235", "858"})
INSS_CODES = frozenset({"843", "858", "998", "812", "826", "989", "8092", "8093"})
FGTS_CODES = frozenset({"23", "32", "35", "813", "996", "8096", "8097", "9637"})
EMPLOYEE_CODES = frozenset({"1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "37", "150", "250", "960", "981", "996", "998"})

VACATION_TERMS = ("ferias",)
TERMINATION_TERMS = ("rescisao", "aviso previo", "fgts 40", "saldo de salario", "multa estabilidade")
LEAVE_TERMS = ("afast", "doenca", "acid trabalho", "aposent invalidez", "lic s venc", "carcere")
PRO_LABORE_TERMS = ("pro labore",)
AUTONOMOUS_TERMS = ("autonomo",)
INSS_TERMS = ("inss", "i n s s")
FGTS_TERMS = ("fgts", "f g t s")
EMPLOYEE_TERMS = (
    "horas normais",
    "horas extras",
    "salario",
    "adicional noturno",
    "insalubridade",
    "periculosidade",
    "comissoes",
    "gratificacao",
    "ferias",
    "fgts do mes",
    "i n s s",
    "inss",
    "afast",
    "rescisao",
)
EMPLOYEE_EXCLUDED_TERMS = ("empregador", "pro labore", "autonomo")


@dataclass(frozen=True, slots=True)
class DominioRubricSignals:
    normalized_name: str
    signals: frozenset[str]


def classify_rubric_signals(code: str, original_name: str) -> DominioRubricSignals:
    normalized_name = normalize_search_text(original_name)
    signals: set[str] = set()

    if code in PRO_LABORE_CODES or _contains_any(normalized_name, PRO_LABORE_TERMS):
        signals.add("has_pro_labore")
    if code in AUTONOMOUS_CODES or _contains_any(normalized_name, AUTONOMOUS_TERMS):
        signals.add("has_autonomous")
    if code in INSS_CODES or _contains_any(normalized_name, INSS_TERMS):
        signals.add("has_inss")
    if code in FGTS_CODES or _contains_any(normalized_name, FGTS_TERMS):
        signals.add("has_fgts")
    if _contains_any(normalized_name, VACATION_TERMS):
        signals.add("has_vacation")
    if _contains_any(normalized_name, TERMINATION_TERMS) or _is_termination_pattern(normalized_name):
        signals.add("has_termination")
    if _contains_any(normalized_name, LEAVE_TERMS):
        signals.add("has_leave")

    if _is_employee_signal(code, normalized_name, signals):
        signals.add("has_employee")

    return DominioRubricSignals(
        normalized_name=normalized_name,
        signals=frozenset(sorted(signals)),
    )


def _contains_any(normalized_name: str, terms: tuple[str, ...]) -> bool:
    return any(term in normalized_name for term in terms)


def _is_employee_signal(code: str, normalized_name: str, signals: set[str]) -> bool:
    if "has_vacation" in signals or "has_termination" in signals or "has_leave" in signals:
        return True
    if "has_pro_labore" in signals or "has_autonomous" in signals:
        return False
    if _contains_any(normalized_name, EMPLOYEE_EXCLUDED_TERMS):
        return False
    if code in EMPLOYEE_CODES:
        return True
    return _contains_any(normalized_name, EMPLOYEE_TERMS)


def _is_termination_pattern(normalized_name: str) -> bool:
    return re.search(r"\b13\b.*\bsalario\b.*\brescisao\b", normalized_name) is not None
