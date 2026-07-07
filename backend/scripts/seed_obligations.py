from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.enums import Department
from backend.app.db.session import SessionLocal
from backend.app.models.fiscal_obligation import FiscalObligation


OBLIGATIONS = (
    {
        "code": "DAS",
        "name": "DAS",
        "category": "SIMPLES",
        "department_default": Department.FISCAL.value,
        "source_priority": ["ACESSORIAS_API", "SITTAX_API", "WATCHER_FILE"],
    },
    {
        "code": "DIFAL",
        "name": "DIFAL",
        "category": "ESTADUAL",
        "department_default": Department.FISCAL.value,
        "source_priority": ["SITTAX_API", "ACESSORIAS_API", "WATCHER_FILE"],
    },
    {
        "code": "ICMS",
        "name": "ICMS",
        "category": "ESTADUAL",
        "department_default": Department.FISCAL.value,
        "source_priority": ["ACESSORIAS_API", "WATCHER_FILE"],
    },
    {
        "code": "ISS",
        "name": "ISS",
        "category": "MUNICIPAL",
        "department_default": Department.FISCAL.value,
        "source_priority": ["ACESSORIAS_API", "WATCHER_FILE"],
    },
    {
        "code": "PIS",
        "name": "PIS",
        "category": "FEDERAL",
        "department_default": Department.FISCAL.value,
        "source_priority": ["ACESSORIAS_API", "WATCHER_FILE"],
    },
    {
        "code": "COFINS",
        "name": "COFINS",
        "category": "FEDERAL",
        "department_default": Department.FISCAL.value,
        "source_priority": ["ACESSORIAS_API", "WATCHER_FILE"],
    },
    {
        "code": "PROTEGE",
        "name": "PROTEGE",
        "category": "ESTADUAL",
        "department_default": Department.FISCAL.value,
        "source_priority": ["WATCHER_FILE", "ACESSORIAS_API"],
    },
    {
        "code": "DCTFWEB",
        "name": "DCTFWeb",
        "category": "FEDERAL",
        "department_default": Department.COMPARTILHADO.value,
        "source_priority": ["DOMINIO_FOLHA", "REINF_API", "FEDERAL_API"],
    },
    {
        "code": "REINF",
        "name": "EFD-Reinf",
        "category": "FEDERAL",
        "department_default": Department.FISCAL.value,
        "source_priority": ["ACESSORIAS_API", "WATCHER_FILE"],
    },
    {
        "code": "EFD_CONTRIBUICOES",
        "name": "EFD Contribuições",
        "category": "FEDERAL",
        "department_default": Department.FISCAL.value,
        "source_priority": ["ACESSORIAS_API", "WATCHER_FILE"],
    },
    {
        "code": "DEFIS",
        "name": "DEFIS",
        "category": "SIMPLES",
        "department_default": Department.FISCAL.value,
        "source_priority": ["ACESSORIAS_API"],
    },
    {
        "code": "DASN_SIMEI",
        "name": "DASN-SIMEI",
        "category": "MEI",
        "department_default": Department.FISCAL.value,
        "source_priority": ["ACESSORIAS_API"],
    },
    {
        "code": "PARCELAMENTO",
        "name": "Parcelamento",
        "category": "PARCELAMENTO",
        "department_default": Department.FISCAL.value,
        "source_priority": ["WATCHER_FILE"],
    },
)


def seed_obligations(session: Session) -> tuple[int, int, int]:
    existing = {
        obligation.code: obligation
        for obligation in session.execute(select(FiscalObligation)).scalars()
    }
    created = 0
    updated = 0

    for item in OBLIGATIONS:
        obligation = existing.get(item["code"])
        if obligation is None:
            session.add(FiscalObligation(**item))
            created += 1
            continue

        changed = False
        for field in ("name", "category", "department_default", "source_priority"):
            value = item[field]
            if getattr(obligation, field) != value:
                setattr(obligation, field, value)
                changed = True
        if not obligation.active:
            obligation.active = True
            changed = True
        if changed:
            updated += 1

    session.commit()
    total = session.scalar(select(func.count()).select_from(FiscalObligation))
    return created, updated, int(total or 0)


def main() -> None:
    session = SessionLocal()
    try:
        created, updated, total = seed_obligations(session)
        print(f"Seed completed. created={created} updated={updated} total={total}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
