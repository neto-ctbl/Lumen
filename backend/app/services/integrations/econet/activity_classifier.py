from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
import json
from pathlib import Path
import re

from sqlalchemy import select
from sqlalchemy.orm import Session
from unidecode import unidecode

from backend.app.core.enums import ActivityType
from backend.app.models.company_activity_type import CompanyActivityType
from backend.app.models.company_cnae import CompanyCnae


CLASSIFIER_SOURCE = "CONCLA_CNAE23"
CLASSIFIER_CONFIDENCE = Decimal("1.00")
SPECIFIC_ACTIVITY_TYPES = {
    ActivityType.TEMPLO_RELIGIOSO.value,
    ActivityType.SERVICOS_MEDICOS_ODONTOLOGICOS.value,
    ActivityType.SERVICOS_IMOBILIARIOS.value,
}
GENERIC_SERVICES_ACTIVITY_TYPE = ActivityType.SERVICOS.value
_KEYWORDS = {
    ActivityType.COMERCIO.value: ("comercio", "varejista", "atacadista"),
    ActivityType.INDUSTRIA.value: ("fabricacao", "industria", "industrializacao"),
    ActivityType.SERVICOS_MEDICOS_ODONTOLOGICOS.value: ("medico", "medicina", "odontologia", "odontologico"),
    ActivityType.SERVICOS_IMOBILIARIOS.value: ("imobiliario", "imoveis", "corretagem imobiliaria", "administracao de imoveis"),
    ActivityType.TEMPLO_RELIGIOSO.value: ("templo", "religiosa", "organizacao religiosa"),
    ActivityType.SERVICOS.value: ("servico", "servicos"),
}
CATALOG_PATH = Path(__file__).resolve().parents[3] / "data" / "company_activity_types" / "company_activity_types_cnae23_concla_catalogo_completo.json"


@dataclass(frozen=True, slots=True)
class CatalogClassification:
    activity_type: str
    rule_id: str | None


def classify_cache_description(description: str) -> tuple[str, ...]:
    normalized = re.sub(r"[^a-z0-9]+", " ", unidecode(description).lower()).strip()
    matches: list[str] = []
    for activity_type, keywords in _KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(keyword)}\b", normalized) for keyword in keywords):
            matches.append(activity_type)
    return tuple(sorted(set(matches)))


@lru_cache(maxsize=1)
def load_activity_type_catalog() -> dict[str, CatalogClassification]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    catalog = payload.get("catalog")
    if not isinstance(catalog, list):
        raise ValueError("Activity type catalog JSON must contain a top-level 'catalog' list.")
    mapping: dict[str, CatalogClassification] = {}
    for item in catalog:
        if not isinstance(item, dict):
            continue
        cnae = str(item.get("normalized") or "").strip()
        activity_type = str(item.get("activity_type") or "").strip()
        if not cnae or not activity_type:
            continue
        mapping[cnae] = CatalogClassification(
            activity_type=activity_type,
            rule_id=str(item.get("rule_id") or "").strip() or None,
        )
    return mapping


def resolve_catalog_activity_type(cnae: str) -> CatalogClassification | None:
    return load_activity_type_catalog().get(str(cnae).strip())


def post_process_company_activity_types(activity_types: set[str]) -> tuple[str, ...]:
    final = set(activity_types)
    if final & SPECIFIC_ACTIVITY_TYPES:
        final.discard(GENERIC_SERVICES_ACTIVITY_TYPE)
    return tuple(sorted(final))


def classify_company_activity_types(
    session: Session,
    *,
    company_id: int,
    dry_run: bool = False,
) -> dict[str, int]:
    active_cnaes = session.scalars(
        select(CompanyCnae).where(CompanyCnae.company_id == company_id, CompanyCnae.active.is_(True))
    ).all()

    desired_raw: set[str] = set()
    unmapped_cnaes = 0
    for cnae_row in active_cnaes:
        classification = resolve_catalog_activity_type(cnae_row.cnae)
        if classification is None:
            unmapped_cnaes += 1
            continue
        desired_raw.add(classification.activity_type)
    desired_types = set(post_process_company_activity_types(desired_raw))

    existing = session.scalars(
        select(CompanyActivityType).where(
            CompanyActivityType.company_id == company_id,
            CompanyActivityType.source == CLASSIFIER_SOURCE,
        )
    ).all()
    existing_by_type = {row.activity_type: row for row in existing}

    created = 0
    unchanged = 0
    deleted = 0

    for activity_type in sorted(desired_types):
        if activity_type in existing_by_type:
            unchanged += 1
            continue
        if not dry_run:
            session.add(
                CompanyActivityType(
                    company_id=company_id,
                    activity_type=activity_type,
                    source=CLASSIFIER_SOURCE,
                    confidence=CLASSIFIER_CONFIDENCE,
                )
            )
        created += 1

    for activity_type, row in existing_by_type.items():
        if activity_type in desired_types:
            continue
        if not dry_run:
            session.delete(row)
        deleted += 1

    if not dry_run:
        session.flush()
    return {
        "created": created,
        "unchanged": unchanged,
        "deleted": deleted,
        "desired": len(desired_types),
        "unmapped_cnaes": unmapped_cnaes,
    }
