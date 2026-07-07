from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from backend.app.core.enums import Department, FiscalRegime
from backend.app.db.session import SessionLocal
from backend.app.models.fiscal_obligation import FiscalObligation
from backend.app.models.fiscal_obligation_rule import FiscalObligationRule
from backend.scripts.seed_obligations import seed_obligations


RULE_DEFINITIONS = (
    {
        "code": "DAS",
        "regime": FiscalRegime.SIMPLES_NACIONAL.value,
        "activity_type": None,
        "rule_type": "APPLICABILITY",
        "condition_payload": {
            "periodicity": "MONTHLY",
            "department": Department.FISCAL.value,
            "source_priority": ["ACESSORIAS_API", "SITTAX_API", "WATCHER_FILE"],
            "requires_evidence_file": True,
            "authority": "CGSN",
            "jurisdiction_scope": "FEDERAL",
            "normative_source_key": "PGDAS_D_DEFIS_MANUAL",
            "applicability_is_indicative": True,
            "final_applicability_source": "ACESSORIAS_API",
        },
    },
    {
        "code": "DEFIS",
        "regime": FiscalRegime.SIMPLES_NACIONAL.value,
        "activity_type": None,
        "rule_type": "APPLICABILITY",
        "condition_payload": {
            "periodicity": "ANNUAL",
            "department": Department.FISCAL.value,
            "authority": "CGSN",
            "jurisdiction_scope": "FEDERAL",
            "normative_source_key": "PGDAS_D_DEFIS_MANUAL",
            "applicability_is_indicative": True,
            "final_applicability_source": "ACESSORIAS_API",
        },
    },
    {
        "code": "DASN_SIMEI",
        "regime": FiscalRegime.MEI.value,
        "activity_type": None,
        "rule_type": "APPLICABILITY",
        "condition_payload": {
            "periodicity": "ANNUAL",
            "department": Department.FISCAL.value,
            "authority": "CGSN",
            "jurisdiction_scope": "FEDERAL",
            "normative_source_key": "DASN_SIMEI_MANUAL",
            "applicability_is_indicative": True,
            "final_applicability_source": "ACESSORIAS_API",
        },
    },
    {
        "code": "DCTFWEB",
        "regime": None,
        "activity_type": None,
        "rule_type": "CONDITIONAL_ORIGIN",
        "condition_payload": {
            "periodicity": "MONTHLY_WHEN_TRIGGERED",
            "origem_esocial_folha_department": Department.DP.value,
            "origem_reinf_department": Department.FISCAL.value,
            "origem_mit_tributos_department": Department.FISCAL.value,
            "origem_multipla_department": Department.COMPARTILHADO.value,
            "next_month_zero_check": True,
            "authority": "RFB",
            "jurisdiction_scope": "FEDERAL",
            "normative_source_key": "DCTFWEB_MANUAL",
            "applicability_is_indicative": True,
            "final_applicability_source": "MANUAL_REVIEW",
        },
    },
    {
        "code": "REINF",
        "regime": None,
        "activity_type": None,
        "rule_type": "CONDITIONAL",
        "condition_payload": {
            "periodicity": "MONTHLY_WHEN_TRIGGERED",
            "department": Department.FISCAL.value,
            "conditional": True,
            "authority": "SPED",
            "jurisdiction_scope": "FEDERAL",
            "normative_source_key": "EFD_REINF_MANUAL",
            "applicability_is_indicative": True,
            "final_applicability_source": "ACESSORIAS_API",
        },
    },
    {
        "code": "DIFAL",
        "regime": None,
        "activity_type": None,
        "rule_type": "CONDITIONAL",
        "condition_payload": {
            "department": Department.FISCAL.value,
            "conditional": True,
            "depends_on": ["SITTAX_API", "ACESSORIAS_API", "WATCHER_FILE", "INTERSTATE_PURCHASES"],
            "candidate_activity_types": ["COMERCIO", "INDUSTRIA"],
            "authority": "SEFAZ_GO",
            "jurisdiction_scope": "STATE_GO",
            "normative_source_key": "SEFAZ_GO_EFD_ICMS_GUIDE",
            "applicability_is_indicative": True,
            "final_applicability_source": "SITTAX_API",
        },
    },
    {
        "code": "ICMS",
        "regime": None,
        "activity_type": None,
        "rule_type": "CONDITIONAL",
        "condition_payload": {
            "department": Department.FISCAL.value,
            "conditional": True,
            "candidate_activity_types": ["COMERCIO", "INDUSTRIA"],
            "authority": "SEFAZ_GO",
            "jurisdiction_scope": "STATE_GO",
            "normative_source_key": "SEFAZ_GO_EFD_ICMS_GUIDE",
            "applicability_is_indicative": True,
            "final_applicability_source": "ACESSORIAS_API",
        },
    },
    {
        "code": "ISS",
        "regime": None,
        "activity_type": None,
        "rule_type": "CONDITIONAL",
        "condition_payload": {
            "department": Department.FISCAL.value,
            "conditional": True,
            "candidate_activity_types": ["SERVICOS", "SERVICOS_MEDICOS_ODONTOLOGICOS", "SERVICOS_IMOBILIARIOS"],
            "authority": "PREFEITURA_ANAPOLIS",
            "jurisdiction_scope": "MUNICIPAL_ANAPOLIS_GO",
            "normative_source_key": "ANAPOLIS_ISSQN_NFSE_PORTARIA_460_2025",
            "applicability_is_indicative": True,
            "final_applicability_source": "ACESSORIAS_API",
        },
    },
    {
        "code": "PIS",
        "regime": FiscalRegime.LUCRO_PRESUMIDO.value,
        "activity_type": None,
        "rule_type": "APPLICABILITY",
        "condition_payload": {
            "periodicity": "MONTHLY",
            "department": Department.FISCAL.value,
            "authority": "RFB",
            "jurisdiction_scope": "FEDERAL",
            "normative_source_key": "MIT_MANUAL",
            "applicability_is_indicative": True,
            "final_applicability_source": "ACESSORIAS_API",
        },
    },
    {
        "code": "PIS",
        "regime": FiscalRegime.LUCRO_REAL.value,
        "activity_type": None,
        "rule_type": "APPLICABILITY",
        "condition_payload": {
            "periodicity": "MONTHLY",
            "department": Department.FISCAL.value,
            "authority": "RFB",
            "jurisdiction_scope": "FEDERAL",
            "normative_source_key": "MIT_MANUAL",
            "applicability_is_indicative": True,
            "final_applicability_source": "ACESSORIAS_API",
        },
    },
    {
        "code": "COFINS",
        "regime": FiscalRegime.LUCRO_PRESUMIDO.value,
        "activity_type": None,
        "rule_type": "APPLICABILITY",
        "condition_payload": {
            "periodicity": "MONTHLY",
            "department": Department.FISCAL.value,
            "authority": "RFB",
            "jurisdiction_scope": "FEDERAL",
            "normative_source_key": "MIT_MANUAL",
            "applicability_is_indicative": True,
            "final_applicability_source": "ACESSORIAS_API",
        },
    },
    {
        "code": "COFINS",
        "regime": FiscalRegime.LUCRO_REAL.value,
        "activity_type": None,
        "rule_type": "APPLICABILITY",
        "condition_payload": {
            "periodicity": "MONTHLY",
            "department": Department.FISCAL.value,
            "authority": "RFB",
            "jurisdiction_scope": "FEDERAL",
            "normative_source_key": "MIT_MANUAL",
            "applicability_is_indicative": True,
            "final_applicability_source": "ACESSORIAS_API",
        },
    },
    {
        "code": "EFD_CONTRIBUICOES",
        "regime": FiscalRegime.LUCRO_PRESUMIDO.value,
        "activity_type": None,
        "rule_type": "APPLICABILITY",
        "condition_payload": {
            "periodicity": "MONTHLY",
            "department": Department.FISCAL.value,
            "authority": "SPED",
            "jurisdiction_scope": "FEDERAL",
            "normative_source_key": "EFD_CONTRIBUICOES_GUIDE",
            "applicability_is_indicative": True,
            "final_applicability_source": "ACESSORIAS_API",
        },
    },
    {
        "code": "EFD_CONTRIBUICOES",
        "regime": FiscalRegime.LUCRO_REAL.value,
        "activity_type": None,
        "rule_type": "APPLICABILITY",
        "condition_payload": {
            "periodicity": "MONTHLY",
            "department": Department.FISCAL.value,
            "authority": "SPED",
            "jurisdiction_scope": "FEDERAL",
            "normative_source_key": "EFD_CONTRIBUICOES_GUIDE",
            "applicability_is_indicative": True,
            "final_applicability_source": "ACESSORIAS_API",
        },
    },
    {
        "code": "PROTEGE",
        "regime": None,
        "activity_type": None,
        "rule_type": "CONDITIONAL",
        "condition_payload": {
            "department": Department.FISCAL.value,
            "conditional": True,
            "candidate_activity_types": ["COMERCIO", "INDUSTRIA"],
            "authority": "SEFAZ_GO",
            "jurisdiction_scope": "STATE_GO",
            "normative_source_key": "SEFAZ_GO_EFD_ICMS_GUIDE",
            "applicability_is_indicative": True,
            "final_applicability_source": "MANUAL_REVIEW",
        },
    },
    {
        "code": "PARCELAMENTO",
        "regime": None,
        "activity_type": None,
        "rule_type": "ACTIVE_INSTALLMENT",
        "condition_payload": {
            "periodicity": "MONTHLY_WHILE_ACTIVE",
            "department": Department.FISCAL.value,
            "requires_evidence_file": True,
            "depends_on_active_installment": True,
            "authority": "PGFN",
            "jurisdiction_scope": "FEDERAL",
            "normative_source_key": "SIMPLES_NACIONAL_PARCELAMENTO_MANUAL",
            "applicability_is_indicative": True,
            "final_applicability_source": "WATCHER_FILE",
        },
    },
)


def seed_obligation_rules(session: Session) -> tuple[int, int, int]:
    seed_obligations(session)
    obligations = {
        obligation.code: obligation
        for obligation in session.execute(select(FiscalObligation)).scalars()
    }
    obligation_codes_by_id = {obligation.id: code for code, obligation in obligations.items()}
    expected_keys = {
        (
            item["code"],
            item["regime"],
            item["activity_type"],
            item["rule_type"],
        )
        for item in RULE_DEFINITIONS
    }
    created = 0
    updated = 0

    for item in RULE_DEFINITIONS:
        obligation = obligations[item["code"]]
        matching_rules = list(
            session.execute(
            select(FiscalObligationRule).where(
                and_(
                    FiscalObligationRule.organization_id.is_(None),
                    FiscalObligationRule.obligation_id == obligation.id,
                    FiscalObligationRule.regime == item["regime"],
                    FiscalObligationRule.activity_type == item["activity_type"],
                    FiscalObligationRule.rule_type == item["rule_type"],
                )
            )
            ).scalars()
        )
        rule = matching_rules[0] if matching_rules else None

        for duplicate in matching_rules[1:]:
            session.delete(duplicate)

        if rule is None:
            session.add(
                FiscalObligationRule(
                    organization_id=None,
                    obligation_id=obligation.id,
                    regime=item["regime"],
                    activity_type=item["activity_type"],
                    rule_type=item["rule_type"],
                    condition_payload=item["condition_payload"],
                    active=True,
                )
            )
            created += 1
            continue

        changed = False
        if rule.condition_payload != item["condition_payload"]:
            rule.condition_payload = item["condition_payload"]
            changed = True
        if not rule.active:
            rule.active = True
            changed = True
        if changed:
            updated += 1

    scoped_codes = {item["code"] for item in RULE_DEFINITIONS}
    obsolete_rules = list(
        session.execute(
            select(FiscalObligationRule)
            .join(FiscalObligation, FiscalObligationRule.obligation_id == FiscalObligation.id)
            .where(
                FiscalObligationRule.organization_id.is_(None),
                FiscalObligation.code.in_(scoped_codes),
            )
        ).scalars()
    )
    for rule in obsolete_rules:
        key = (
            obligation_codes_by_id[rule.obligation_id],
            rule.regime,
            rule.activity_type,
            rule.rule_type,
        )
        if key not in expected_keys:
            session.delete(rule)

    session.commit()
    total = session.scalar(select(func.count()).select_from(FiscalObligationRule))
    return created, updated, int(total or 0)


def main() -> None:
    session = SessionLocal()
    try:
        created, updated, total = seed_obligation_rules(session)
        print(f"Seed completed. created={created} updated={updated} total={total}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
