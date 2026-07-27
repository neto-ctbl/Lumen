from __future__ import annotations

from decimal import Decimal
import re

from sqlalchemy import select
from sqlalchemy.orm import Session
from unidecode import unidecode

from backend.app.core.enums import ActivityType
from backend.app.models.company_activity_type import CompanyActivityType
from backend.app.models.company_cnae import CompanyCnae
from backend.app.models.econet_cnae_cache import EconetCnaeCache


CLASSIFIER_SOURCE = "ECONET"
CLASSIFIER_CONFIDENCE = Decimal("1.00")
_KEYWORDS = {
    ActivityType.COMERCIO.value: ("comercio", "varejista", "atacadista"),
    ActivityType.INDUSTRIA.value: ("fabricacao", "industria", "industrializacao"),
    ActivityType.SERVICOS_MEDICOS_ODONTOLOGICOS.value: ("medico", "medicina", "odontologia", "odontologico"),
    ActivityType.SERVICOS_IMOBILIARIOS.value: ("imobiliario", "imoveis", "corretagem imobiliaria", "administracao de imoveis"),
    ActivityType.TEMPLO_RELIGIOSO.value: ("templo", "religiosa", "organizacao religiosa"),
    ActivityType.SERVICOS.value: ("servico", "servicos"),
}


def classify_cache_description(description: str) -> tuple[str, ...]:
    normalized = re.sub(r"[^a-z0-9]+", " ", unidecode(description).lower()).strip()
    matches: list[str] = []
    for activity_type, keywords in _KEYWORDS.items():
        if any(re.search(rf"\b{re.escape(keyword)}\b", normalized) for keyword in keywords):
            matches.append(activity_type)
    return tuple(sorted(set(matches)))


def classify_company_activity_types(
    session: Session,
    *,
    company_id: int,
    dry_run: bool = False,
) -> dict[str, int]:
    active_cnaes = session.scalars(
        select(CompanyCnae).where(CompanyCnae.company_id == company_id, CompanyCnae.active.is_(True))
    ).all()
    if not active_cnaes:
        return {"created": 0, "unchanged": 0}
    caches = {
        row.cnae: row
        for row in session.scalars(select(EconetCnaeCache).where(EconetCnaeCache.cnae.in_([item.cnae for item in active_cnaes]))).all()
    }
    desired = set()
    for cnae in active_cnaes:
        cache = caches.get(cnae.cnae)
        if cache is None:
            continue
        desired.update(classify_cache_description(cache.description))
    existing = session.scalars(
        select(CompanyActivityType).where(
            CompanyActivityType.company_id == company_id,
            CompanyActivityType.source == CLASSIFIER_SOURCE,
        )
    ).all()
    existing_types = {row.activity_type for row in existing}
    created = 0
    unchanged = 0
    for activity_type in sorted(desired):
        if activity_type in existing_types:
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
    if not dry_run:
        session.flush()
    return {"created": created, "unchanged": unchanged}
