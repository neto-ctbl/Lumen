from __future__ import annotations

from sqlalchemy import func, select

from backend.app.core.enums import Department
from backend.app.models.fiscal_obligation import FiscalObligation
from backend.scripts.seed_obligations import OBLIGATIONS, seed_obligations


def test_seed_creates_all_required_obligations(db_session) -> None:
    created, updated, total = seed_obligations(db_session)

    assert created == 13
    assert updated == 0
    assert total == 13
    assert db_session.scalar(select(func.count()).select_from(FiscalObligation)) == 13


def test_seed_is_idempotent(db_session) -> None:
    seed_obligations(db_session)
    created, updated, total = seed_obligations(db_session)

    assert created == 0
    assert updated == 0
    assert total == 13
    assert db_session.scalar(select(func.count()).select_from(FiscalObligation)) == 13


def test_seed_preserves_required_codes_and_departments(db_session) -> None:
    seed_obligations(db_session)

    obligations = {
        obligation.code: obligation
        for obligation in db_session.execute(select(FiscalObligation).order_by(FiscalObligation.code)).scalars()
    }

    assert set(obligations) == {item["code"] for item in OBLIGATIONS}
    assert obligations["DAS"].department_default == Department.FISCAL.value
    assert obligations["DAS"].source_priority == ["ACESSORIAS_API", "SITTAX_API", "WATCHER_FILE"]
    assert obligations["DCTFWEB"].department_default == Department.COMPARTILHADO.value
    assert obligations["PARCELAMENTO"].department_default == Department.FISCAL.value
    assert obligations["REINF"].name == "EFD-Reinf"


def test_seed_does_not_duplicate_by_code(db_session) -> None:
    seed_obligations(db_session)
    seed_obligations(db_session)

    duplicates = (
        db_session.execute(
            select(FiscalObligation.code, func.count(FiscalObligation.id))
            .group_by(FiscalObligation.code)
            .having(func.count(FiscalObligation.id) > 1)
        )
        .all()
    )

    assert duplicates == []
