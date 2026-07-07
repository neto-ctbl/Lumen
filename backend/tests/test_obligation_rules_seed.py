from __future__ import annotations

from sqlalchemy import func, select

from backend.app.core.enums import FISCAL_REGIME_LABELS, FiscalRegime
from backend.app.models.fiscal_obligation_status import FiscalObligationStatus
from backend.app.models.fiscal_obligation import FiscalObligation
from backend.app.models.fiscal_obligation_rule import FiscalObligationRule
from backend.scripts.seed_obligations import seed_obligations
from backend.scripts.seed_obligation_rules import seed_obligation_rules


def _rules_by_code(db_session) -> dict[str, list[FiscalObligationRule]]:
    rows = db_session.execute(
        select(FiscalObligation.code, FiscalObligationRule)
        .join(FiscalObligationRule, FiscalObligationRule.obligation_id == FiscalObligation.id)
        .where(FiscalObligationRule.organization_id.is_(None))
    ).all()
    grouped: dict[str, list[FiscalObligationRule]] = {}
    for code, rule in rows:
        grouped.setdefault(code, []).append(rule)
    return grouped


def test_seed_obligation_rules_is_idempotent(db_session) -> None:
    seed_obligations(db_session)
    created, updated, total = seed_obligation_rules(db_session)
    assert created == 16
    assert updated == 0
    assert total == 16

    created, updated, total = seed_obligation_rules(db_session)
    assert created == 0
    assert updated == 0
    assert total == 16
    assert db_session.scalar(select(func.count()).select_from(FiscalObligationRule)) == 16


def test_required_rules_exist(db_session) -> None:
    seed_obligation_rules(db_session)

    rules = _rules_by_code(db_session)
    for code in ("DAS", "DCTFWEB", "PARCELAMENTO", "DEFIS", "DASN_SIMEI"):
        assert code in rules
    assert sorted(rule.regime for rule in rules["PIS"]) == [
        FiscalRegime.LUCRO_PRESUMIDO.value,
        FiscalRegime.LUCRO_REAL.value,
    ]
    assert sorted(rule.regime for rule in rules["COFINS"]) == [
        FiscalRegime.LUCRO_PRESUMIDO.value,
        FiscalRegime.LUCRO_REAL.value,
    ]
    assert sorted(rule.regime for rule in rules["EFD_CONTRIBUICOES"]) == [
        FiscalRegime.LUCRO_PRESUMIDO.value,
        FiscalRegime.LUCRO_REAL.value,
    ]


def test_dctfweb_payload_is_seeded(db_session) -> None:
    seed_obligation_rules(db_session)

    rule = _rules_by_code(db_session)["DCTFWEB"][0]
    payload = rule.condition_payload or {}

    assert rule.rule_type == "CONDITIONAL_ORIGIN"
    assert payload["periodicity"] == "MONTHLY_WHEN_TRIGGERED"
    assert payload["origem_esocial_folha_department"] == "DP"
    assert payload["origem_reinf_department"] == "FISCAL"
    assert payload["origem_mit_tributos_department"] == "FISCAL"
    assert payload["origem_multipla_department"] == "COMPARTILHADO"
    assert payload["next_month_zero_check"] is True
    assert payload["authority"] == "RFB"
    assert payload["jurisdiction_scope"] == "FEDERAL"
    assert payload["normative_source_key"] == "DCTFWEB_MANUAL"
    assert payload["applicability_is_indicative"] is True
    assert payload["final_applicability_source"] == "MANUAL_REVIEW"


def test_das_payload_is_seeded(db_session) -> None:
    seed_obligation_rules(db_session)

    rule = _rules_by_code(db_session)["DAS"][0]
    payload = rule.condition_payload or {}

    assert rule.regime == FiscalRegime.SIMPLES_NACIONAL.value
    assert rule.rule_type == "APPLICABILITY"
    assert payload["periodicity"] == "MONTHLY"
    assert payload["department"] == "FISCAL"
    assert payload["source_priority"] == ["ACESSORIAS_API", "SITTAX_API", "WATCHER_FILE"]
    assert payload["requires_evidence_file"] is True
    assert payload["authority"] == "CGSN"
    assert payload["jurisdiction_scope"] == "FEDERAL"
    assert payload["normative_source_key"] == "PGDAS_D_DEFIS_MANUAL"
    assert payload["applicability_is_indicative"] is True
    assert payload["final_applicability_source"] == "ACESSORIAS_API"


def test_seed_does_not_create_obligation_statuses(db_session) -> None:
    seed_obligation_rules(db_session)

    assert db_session.scalar(select(func.count()).select_from(FiscalObligationStatus)) == 0


def test_imune_isenta_exists_in_regime_catalog() -> None:
    assert FiscalRegime.IMUNE_ISENTA.value == "IMUNE_ISENTA"
    assert FISCAL_REGIME_LABELS[FiscalRegime.IMUNE_ISENTA] == "Imune/Isenta"
