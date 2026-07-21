from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from typing import Any

from bs4 import BeautifulSoup
from unidecode import unidecode

from backend.app.core.enums import ActivityType, EconetSemanticStatus
from backend.app.services.integrations.econet.errors import (
    EconetAuthenticationPageDetectedError,
    EconetCnaeValidationError,
    EconetParserError,
    EconetUnexpectedContractError,
)


PARSER_VERSION = "1"
CONTRACT_VERSION = "s8.1"
SAFE_OBLIGATION_NAME_MAP = {
    "dctfweb": "DCTFWEB",
    "efd contribuicoes": "EFD_CONTRIBUICOES",
    "efd reinf": "REINF",
}
CNAE_DIGITS_RE = re.compile(r"\d")
CNAE_FORMATTED_RE = re.compile(r"\b\d{4}-\d/\d{2}\b")
PERCENT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


@dataclass(frozen=True, slots=True)
class EconetSearchResult:
    econet_id_cnae: str
    cnae: str
    cnae_formatted: str
    description: str


@dataclass(frozen=True, slots=True)
class EconetCnaeDetail:
    econet_id_cnae: str | None
    cnae: str
    cnae_formatted: str
    description: str
    activity_notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EconetPresumedProfitResult:
    status: str
    allowed: bool | None
    irpj_rate: Decimal | None
    csll_rate: Decimal | None
    reason_text: str


@dataclass(frozen=True, slots=True)
class EconetActualProfitResult:
    scope: str
    status: str
    mandatory: bool | None
    reason_text: str


@dataclass(frozen=True, slots=True)
class EconetSimplesResult:
    status: str
    allowed: bool | None
    annex_default: str | None
    annex_conditional: str | None
    factor_r_applicable: bool | None
    factor_r_threshold: Decimal | None
    factor_r_status: str
    reason_text: str


@dataclass(frozen=True, slots=True)
class EconetMeiResult:
    status: str
    allowed: bool | None
    occupation: str | None
    reason_text: str


@dataclass(frozen=True, slots=True)
class EconetObligationItem:
    name: str
    mapped_code: str | None


@dataclass(frozen=True, slots=True)
class EconetObligationTabs:
    groups: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EconetObligationResult:
    scope: str
    status: str
    items: tuple[EconetObligationItem, ...]
    reason_text: str | None
    unmapped_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EconetNormalizedCnaeResult:
    cnae: str
    cnae_formatted: str
    description: str
    econet_id_cnae: str
    activity_types: tuple[str, ...]
    simples_status: str
    simples_allowed: bool | None
    simples_annex_default: str | None
    simples_annex_conditional: str | None
    factor_r_applicable: bool | None
    factor_r_threshold: Decimal | None
    mei_status: str
    mei_allowed: bool | None
    mei_occupation: str | None
    presumed_profit_status: str
    presumed_profit_allowed: bool | None
    presumed_profit_irpj_rate: Decimal | None
    presumed_profit_csll_rate: Decimal | None
    actual_profit_status: str
    actual_profit_mandatory: bool | None
    obligations_general: dict[str, Any]
    obligations_simples: dict[str, Any]
    obligations_simei: dict[str, Any]
    unmapped_obligations: tuple[str, ...]
    normalized_payload: dict[str, Any]
    parse_status: str
    parser_version: str
    content_hash: str


def normalize_cnae(value: str) -> str:
    digits = "".join(CNAE_DIGITS_RE.findall(value or ""))
    if len(digits) != 7:
        raise EconetCnaeValidationError("Expected CNAE with exactly 7 digits.")
    return digits


def format_cnae(value: str) -> str:
    digits = normalize_cnae(value)
    return f"{digits[:4]}-{digits[4]}/{digits[5:]}"


def parse_search_results(html: str | bytes) -> list[EconetSearchResult]:
    soup = _parse_html(html, expected_markers=("idcnae", "CNAE"))
    results: list[EconetSearchResult] = []
    for radio in soup.find_all("input", attrs={"name": "idcnae"}):
        econet_id = _clean_text(radio.get("value"))
        if not econet_id:
            raise EconetUnexpectedContractError("Search result item is missing internal Econet ID.")
        label = radio.find_parent("label")
        row = radio.find_parent("tr")
        cnae_text = _clean_text(label.get_text(" ", strip=True) if label else "")
        cnae_match = CNAE_FORMATTED_RE.search(cnae_text)
        if cnae_match is None:
            raise EconetUnexpectedContractError("Search result item is missing formatted CNAE.")
        description = ""
        if row is not None:
            cells = row.find_all("td")
            if len(cells) >= 2:
                description = _clean_text(cells[1].get_text(" ", strip=True))
        if not description:
            raise EconetUnexpectedContractError("Search result item is missing description.")
        results.append(
            EconetSearchResult(
                econet_id_cnae=econet_id,
                cnae=normalize_cnae(cnae_match.group(0)),
                cnae_formatted=format_cnae(cnae_match.group(0)),
                description=description,
            )
        )
    if not results:
        raise EconetUnexpectedContractError("No valid CNAE results were found in search response.")
    return results


def parse_cnae_detail(html: str | bytes) -> EconetCnaeDetail:
    soup = _parse_html(html, expected_markers=("Consulta por CNAE", "CNAE:"))
    text = soup.get_text(" ", strip=True)
    cnae_match = CNAE_FORMATTED_RE.search(text)
    if cnae_match is None:
        raise EconetUnexpectedContractError("CNAE detail page is missing formatted CNAE.")
    econet_id = _clean_text((soup.find(attrs={"data-econet-id": True}) or {}).get("data-econet-id"))
    description = _extract_labeled_value(text, "Descricao:")
    if not description:
        raise EconetUnexpectedContractError("CNAE detail page is missing description.")
    return EconetCnaeDetail(
        econet_id_cnae=econet_id or None,
        cnae=normalize_cnae(cnae_match.group(0)),
        cnae_formatted=format_cnae(cnae_match.group(0)),
        description=description,
        activity_notes=(),
    )


def parse_lucro_presumido(html: str | bytes) -> EconetPresumedProfitResult:
    soup = _parse_html(html, expected_markers=("Lucro Presumido",))
    text = _clean_text(soup.get_text(" ", strip=True))
    status = EconetSemanticStatus.UNKNOWN
    allowed: bool | None = None
    if "possibilidade" in _norm(text) or "permitid" in _norm(text):
        status = EconetSemanticStatus.ALLOWED
        allowed = True
    elif "imped" in _norm(text) or "proibid" in _norm(text):
        status = EconetSemanticStatus.PROHIBITED
        allowed = False
    irpj_rate = _extract_named_percent(text, "IRPJ")
    csll_rate = _extract_named_percent(text, "CSLL")
    return EconetPresumedProfitResult(
        status=status,
        allowed=allowed,
        irpj_rate=irpj_rate,
        csll_rate=csll_rate,
        reason_text=text,
    )


def parse_lucro_real_trimestral(html: str | bytes) -> EconetActualProfitResult:
    return _parse_actual_profit(html, scope="TRIMESTRAL", expected_marker="Lucro Real Trimestral")


def parse_lucro_real_estimativa(html: str | bytes) -> EconetActualProfitResult:
    return _parse_actual_profit(html, scope="ESTIMATIVA", expected_marker="Lucro Real por Estimativa")


def parse_simples_nacional(html: str | bytes) -> EconetSimplesResult:
    soup = _parse_html(html, expected_markers=("Simples Nacional",))
    text = _clean_text(soup.get_text(" ", strip=True))
    norm_text = _norm(text)
    if "impedida ao simples nacional" in norm_text or "impedido ao simples nacional" in norm_text:
        return EconetSimplesResult(
            status=EconetSemanticStatus.PROHIBITED,
            allowed=False,
            annex_default=None,
            annex_conditional=None,
            factor_r_applicable=None,
            factor_r_threshold=None,
            factor_r_status=EconetSemanticStatus.NOT_OBSERVED,
            reason_text=text,
        )

    annexes = re.findall(r"Anexo\s+([IVX]+)", text, flags=re.IGNORECASE)
    annex_default = annexes[0].upper() if annexes else None
    annex_conditional = annexes[1].upper() if len(annexes) > 1 else None
    allowed = True if "permitida ao simples nacional" in norm_text or annex_default is not None else None
    status = EconetSemanticStatus.ALLOWED if allowed else EconetSemanticStatus.UNKNOWN
    factor_r_match = re.search(r"Fator\s+R\s*(?:>=|>|igual a)?\s*(\d+(?:[.,]\d+)?)\s*%", text, flags=re.IGNORECASE)
    factor_r_threshold = _to_decimal(factor_r_match.group(1)) if factor_r_match else None
    factor_r_applicable = True if factor_r_match else None
    factor_r_status = EconetSemanticStatus.PARSED if factor_r_match else EconetSemanticStatus.NOT_OBSERVED
    return EconetSimplesResult(
        status=status,
        allowed=allowed,
        annex_default=annex_default,
        annex_conditional=annex_conditional,
        factor_r_applicable=factor_r_applicable,
        factor_r_threshold=factor_r_threshold,
        factor_r_status=factor_r_status,
        reason_text=text,
    )


def parse_empreendedor_individual(html: str | bytes) -> EconetMeiResult:
    soup = _parse_html(html, expected_markers=("Empreendedor Individual",))
    text = _clean_text(soup.get_text(" ", strip=True))
    norm_text = _norm(text)
    if "nao e possivel o enquadramento como microempreendedor individual" in norm_text:
        return EconetMeiResult(
            status=EconetSemanticStatus.NOT_ALLOWED,
            allowed=False,
            occupation=None,
            reason_text=text,
        )

    occupation = None
    occupation_match = re.search(r"Ocupacao correspondente:\s*([^\.]+)", text, flags=re.IGNORECASE)
    if occupation_match:
        occupation = _clean_text(occupation_match.group(1))
    allowed = True if "permitido ao mei" in norm_text or "possivel o enquadramento" in norm_text else None
    status = EconetSemanticStatus.ALLOWED if allowed else EconetSemanticStatus.UNKNOWN
    return EconetMeiResult(status=status, allowed=allowed, occupation=occupation, reason_text=text)


def parse_obligation_tabs(html: str | bytes) -> EconetObligationTabs:
    soup = _parse_html(html, expected_markers=("PJ em Geral", "Optante Simples Nacional", "Optante SIMEI"))
    groups = tuple(
        _clean_text(node.get_text(" ", strip=True))
        for node in soup.select(".grupo-obrigacoes")
        if _clean_text(node.get_text(" ", strip=True))
    )
    if not groups:
        raise EconetUnexpectedContractError("Obligation tabs response is missing expected groups.")
    return EconetObligationTabs(groups=groups)


def parse_obligations_general(html: str | bytes) -> EconetObligationResult:
    soup = _parse_html(html, expected_markers=("PJ em Geral", "Obrigacao"))
    table = soup.find("table", {"class": "tabelaResultados"})
    if table is None:
        raise EconetUnexpectedContractError("General obligations response is missing results table.")
    items: list[EconetObligationItem] = []
    unmapped: list[str] = []
    for row in table.find_all("tr"):
        style = _norm(_clean_text(row.get("style")))
        if "display: none" in style:
            continue
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        name = _clean_text(cells[0].get_text(" ", strip=True))
        second_column = _clean_text(cells[1].get_text(" ", strip=True))
        if not name or name.lower() == "obrigacao":
            continue
        mapped_code = _map_safe_obligation_name(name)
        if mapped_code is None:
            unmapped.append(name)
        items.append(EconetObligationItem(name=name, mapped_code=mapped_code))
        if second_column == "-":
            continue
    status = EconetSemanticStatus.PARSED if items else EconetSemanticStatus.EMPTY
    return EconetObligationResult(
        scope="PJ_GERAL",
        status=status,
        items=tuple(sorted(items, key=lambda item: item.name)),
        reason_text=_clean_text(soup.get_text(" ", strip=True)),
        unmapped_names=tuple(sorted(set(unmapped))),
    )


def parse_obligations_simples(html: str | bytes) -> EconetObligationResult:
    soup = _parse_html(html, expected_markers=("Simples Nacional",))
    text = _clean_text(soup.get_text(" ", strip=True))
    norm_text = _norm(text)
    if "impedida ao simples nacional" in norm_text or "impedido ao simples nacional" in norm_text:
        return EconetObligationResult(
            scope="SIMPLES_NACIONAL",
            status=EconetSemanticStatus.REGIME_PROHIBITED,
            items=(),
            reason_text=text,
        )
    return EconetObligationResult(scope="SIMPLES_NACIONAL", status=EconetSemanticStatus.EMPTY, items=(), reason_text=text)


def parse_obligations_simei(html: str | bytes) -> EconetObligationResult:
    soup = _parse_html(html, expected_markers=("Microempreendedor Individual",))
    text = _clean_text(soup.get_text(" ", strip=True))
    norm_text = _norm(text)
    if "nao e possivel o enquadramento como microempreendedor individual" in norm_text:
        return EconetObligationResult(
            scope="SIMEI",
            status=EconetSemanticStatus.REGIME_NOT_ALLOWED,
            items=(),
            reason_text=text,
        )
    return EconetObligationResult(scope="SIMEI", status=EconetSemanticStatus.EMPTY, items=(), reason_text=text)


def build_normalized_cnae_result(
    *,
    detail: EconetCnaeDetail,
    presumed_profit: EconetPresumedProfitResult,
    actual_profit_trimestral: EconetActualProfitResult,
    actual_profit_estimativa: EconetActualProfitResult,
    simples: EconetSimplesResult,
    mei: EconetMeiResult,
    obligations_general: EconetObligationResult,
    obligations_simples: EconetObligationResult,
    obligations_simei: EconetObligationResult,
) -> EconetNormalizedCnaeResult:
    actual_profit_status, actual_profit_mandatory = _merge_actual_profit_status(
        actual_profit_trimestral,
        actual_profit_estimativa,
    )
    unmapped_obligations = tuple(
        sorted(
            set(obligations_general.unmapped_names)
            | set(obligations_simples.unmapped_names)
            | set(obligations_simei.unmapped_names)
        )
    )
    payload = {
        "contract_version": CONTRACT_VERSION,
        "parser_version": PARSER_VERSION,
        "cnae": {
            "normalized": detail.cnae,
            "formatted": detail.cnae_formatted,
            "description": detail.description,
            "econet_id_cnae": detail.econet_id_cnae,
        },
        "activity_types": [],
        "simples": {
            "status": simples.status,
            "allowed": simples.allowed,
            "annex_default": simples.annex_default,
            "annex_conditional": simples.annex_conditional,
            "factor_r_applicable": simples.factor_r_applicable,
            "factor_r_threshold": simples.factor_r_threshold,
            "factor_r_status": simples.factor_r_status,
            "reason_text": simples.reason_text,
        },
        "mei": {
            "status": mei.status,
            "allowed": mei.allowed,
            "occupation": mei.occupation,
            "reason_text": mei.reason_text,
        },
        "presumed_profit": {
            "status": presumed_profit.status,
            "allowed": presumed_profit.allowed,
            "irpj_rate": presumed_profit.irpj_rate,
            "csll_rate": presumed_profit.csll_rate,
            "reason_text": presumed_profit.reason_text,
        },
        "actual_profit": {
            "status": actual_profit_status,
            "mandatory": actual_profit_mandatory,
            "trimestral": {
                "status": actual_profit_trimestral.status,
                "mandatory": actual_profit_trimestral.mandatory,
                "reason_text": actual_profit_trimestral.reason_text,
            },
            "estimativa": {
                "status": actual_profit_estimativa.status,
                "mandatory": actual_profit_estimativa.mandatory,
                "reason_text": actual_profit_estimativa.reason_text,
            },
        },
        "obligations": {
            "general": _obligation_result_payload(obligations_general),
            "simples": _obligation_result_payload(obligations_simples),
            "simei": _obligation_result_payload(obligations_simei),
        },
        "unmapped_obligations": list(unmapped_obligations),
    }
    payload = _json_ready(payload)
    content_hash = compute_content_hash(payload)
    return EconetNormalizedCnaeResult(
        cnae=detail.cnae,
        cnae_formatted=detail.cnae_formatted,
        description=detail.description,
        econet_id_cnae=detail.econet_id_cnae or "",
        activity_types=(),
        simples_status=simples.status,
        simples_allowed=simples.allowed,
        simples_annex_default=simples.annex_default,
        simples_annex_conditional=simples.annex_conditional,
        factor_r_applicable=simples.factor_r_applicable,
        factor_r_threshold=simples.factor_r_threshold,
        mei_status=mei.status,
        mei_allowed=mei.allowed,
        mei_occupation=mei.occupation,
        presumed_profit_status=presumed_profit.status,
        presumed_profit_allowed=presumed_profit.allowed,
        presumed_profit_irpj_rate=presumed_profit.irpj_rate,
        presumed_profit_csll_rate=presumed_profit.csll_rate,
        actual_profit_status=actual_profit_status,
        actual_profit_mandatory=actual_profit_mandatory,
        obligations_general=payload["obligations"]["general"],
        obligations_simples=payload["obligations"]["simples"],
        obligations_simei=payload["obligations"]["simei"],
        unmapped_obligations=unmapped_obligations,
        normalized_payload=payload,
        parse_status="PARSED",
        parser_version=PARSER_VERSION,
        content_hash=content_hash,
    )


def compute_content_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(_json_ready(payload), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_actual_profit(html: str | bytes, *, scope: str, expected_marker: str) -> EconetActualProfitResult:
    soup = _parse_html(html, expected_markers=(expected_marker,))
    text = _clean_text(soup.get_text(" ", strip=True))
    norm_text = _norm(text)
    if "nao obrigat" in norm_text:
        return EconetActualProfitResult(
            scope=scope,
            status=EconetSemanticStatus.NOT_MANDATORY,
            mandatory=False,
            reason_text=text,
        )
    if "sem inferencia automatica" in norm_text:
        return EconetActualProfitResult(scope=scope, status=EconetSemanticStatus.UNKNOWN, mandatory=None, reason_text=text)
    if "obrigator" in norm_text:
        return EconetActualProfitResult(scope=scope, status=EconetSemanticStatus.MANDATORY, mandatory=True, reason_text=text)
    if "possibil" in norm_text:
        return EconetActualProfitResult(scope=scope, status=EconetSemanticStatus.ALLOWED, mandatory=False, reason_text=text)
    return EconetActualProfitResult(scope=scope, status=EconetSemanticStatus.UNKNOWN, mandatory=None, reason_text=text)


def _merge_actual_profit_status(
    trimestral: EconetActualProfitResult,
    estimativa: EconetActualProfitResult,
) -> tuple[str, bool | None]:
    statuses = [trimestral, estimativa]
    if any(result.status == EconetSemanticStatus.MANDATORY for result in statuses):
        return EconetSemanticStatus.MANDATORY, True
    if any(result.status == EconetSemanticStatus.NOT_MANDATORY for result in statuses):
        return EconetSemanticStatus.NOT_MANDATORY, False
    if any(result.status == EconetSemanticStatus.ALLOWED for result in statuses):
        return EconetSemanticStatus.ALLOWED, False
    if all(result.status == EconetSemanticStatus.UNKNOWN for result in statuses):
        return EconetSemanticStatus.UNKNOWN, None
    return EconetSemanticStatus.NOT_OBSERVED, None


def _obligation_result_payload(result: EconetObligationResult) -> dict[str, Any]:
    return {
        "scope": result.scope,
        "status": result.status,
        "items": [
            {
                "name": item.name,
                "mapped_code": item.mapped_code,
            }
            for item in sorted(result.items, key=lambda current: current.name)
        ],
        "reason_text": result.reason_text,
    }


def _map_safe_obligation_name(name: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", " ", unidecode(name).lower()).strip()
    return SAFE_OBLIGATION_NAME_MAP.get(normalized)


def _extract_named_percent(text: str, label: str) -> Decimal | None:
    match = re.search(rf"{label}\s*:\s*(\d+(?:[.,]\d+)?)\s*%", text, flags=re.IGNORECASE)
    return _to_decimal(match.group(1)) if match else None


def _to_decimal(value: str) -> Decimal:
    try:
        return Decimal(value.replace(".", "").replace(",", ".") if "," in value and "." in value else value.replace(",", "."))
    except InvalidOperation as exc:
        raise EconetParserError("Unable to parse numeric percentage value.") from exc


def _extract_labeled_value(text: str, label: str) -> str:
    if label not in text:
        return ""
    _, _, tail = text.partition(label)
    chunks = tail.strip().split()
    return _clean_text(" ".join(chunks[:12]))


def _parse_html(html: str | bytes, *, expected_markers: tuple[str, ...]) -> BeautifulSoup:
    if isinstance(html, bytes):
        html = html.decode("utf-8")
    if not html or not html.strip():
        raise EconetUnexpectedContractError("Econet HTML is empty.")

    soup = BeautifulSoup(html, "lxml")
    text = _clean_text(soup.get_text(" ", strip=True))
    norm_text = _norm(text)
    if not text:
        raise EconetUnexpectedContractError("Econet HTML does not contain readable text.")
    if any(marker in norm_text for marker in ("g recaptcha", "captcha")):
        raise EconetAuthenticationPageDetectedError("Captcha page detected in Econet HTML.")
    if any(marker in norm_text for marker in ("login", "senha", "entrar")) and "consulta por cnae" not in norm_text:
        raise EconetAuthenticationPageDetectedError("Authentication page detected in Econet HTML.")
    if expected_markers and not any(marker.lower() in text.lower() for marker in expected_markers):
        raise EconetUnexpectedContractError("Unexpected Econet HTML contract.")
    return soup


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", unidecode(value).lower()).strip()


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, ActivityType):
        return value.value
    if isinstance(value, dict):
        return {key: _json_ready(val) for key, val in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if is_dataclass(value):
        return _json_ready(asdict(value))
    return value
