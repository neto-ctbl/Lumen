from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.enums import FiscalRegime
from backend.app.models.acessorias_company_snapshot import AcessoriasCompanySnapshot
from backend.app.models.dominio_payroll import DominioPayrollCompanyMovement
from backend.app.models.external_company import ExternalCompany
from backend.app.models.organization import Organization
from backend.app.models.sittax_apuracao_snapshot import SittaxApuracaoSnapshot
from backend.app.services.factor_r import FactorRPotentialResult, get_company_factor_r_potential
from backend.app.services.integrations.acessorias.regime import resolve_acessorias_regime
from backend.app.services.integrations.dominio.manual_company_codes import get_manual_dominio_company_codes
from backend.app.services.integrations.dominio.selection_scope import normalize_target_list_sha256


FILTER_ACTION_INCLUDE = "INCLUDE"
FILTER_ACTION_REMOVE = "REMOVE"
FILTER_ACTION_REVIEW = "REVIEW"
FILTER_ACTION_MISSING_DOMINIO_CODE = "MISSING_DOMINIO_CODE"


@dataclass(frozen=True, slots=True)
class DominioFactorRTargetRow:
    dominio_company_code: str | None
    company_cnpj: str
    company_name: str
    is_active: bool
    tax_regime: str | None
    is_mei: bool | None
    factor_r_potential: bool | None
    factor_r_effectively_used: bool | None
    factor_r_cnae_codes: tuple[str, ...]
    factor_r_reason: str
    filter_action: str

    def to_csv_row(self) -> dict[str, str]:
        return {
            "dominio_company_code": self.dominio_company_code or "",
            "company_cnpj": self.company_cnpj,
            "company_name": self.company_name,
            "is_active": _stringify_bool(self.is_active),
            "tax_regime": self.tax_regime or "",
            "is_mei": _stringify_optional_bool(self.is_mei),
            "factor_r_potential": _stringify_optional_bool(self.factor_r_potential),
            "factor_r_effectively_used": _stringify_optional_bool(self.factor_r_effectively_used),
            "factor_r_cnae_codes": ",".join(self.factor_r_cnae_codes),
            "factor_r_reason": self.factor_r_reason,
            "filter_action": self.filter_action,
        }


@dataclass(frozen=True, slots=True)
class DominioFactorRTargetExport:
    organization_slug: str
    rows: tuple[DominioFactorRTargetRow, ...]
    target_company_count: int
    target_list_sha256: str
    summary_payload: dict[str, object]

    def terminal_summary(self) -> dict[str, object]:
        include = sum(1 for row in self.rows if row.filter_action == FILTER_ACTION_INCLUDE)
        missing_code = sum(1 for row in self.rows if row.filter_action == FILTER_ACTION_MISSING_DOMINIO_CODE)
        review = sum(1 for row in self.rows if row.filter_action == FILTER_ACTION_REVIEW)
        remove = sum(1 for row in self.rows if row.filter_action == FILTER_ACTION_REMOVE)
        return {
            "organization_slug": self.organization_slug,
            "selection_scope": "FACTOR_R",
            "rows_total": len(self.rows),
            "target_company_count": self.target_company_count,
            "target_list_sha256": self.target_list_sha256,
            "include": include,
            "missing_dominio_code": missing_code,
            "review": review,
            "remove": remove,
        }


def build_dominio_factor_r_targets(session: Session, *, organization: Organization) -> DominioFactorRTargetExport:
    companies = session.scalars(
        select(ExternalCompany)
        .where(ExternalCompany.organization_id == organization.id)
        .order_by(ExternalCompany.razao_social.asc(), ExternalCompany.id.asc())
    ).all()
    company_ids = [company.id for company in companies]
    snapshots = _latest_snapshot_map(session, organization_id=organization.id, company_ids=company_ids)
    dominio_code_by_cnpj = _dominio_code_map(
        session,
        organization_id=organization.id,
        organization_slug=organization.slug,
    )
    effective_use_by_company_id = _factor_r_effective_use_map(session, organization_id=organization.id, company_ids=company_ids)

    rows: list[DominioFactorRTargetRow] = []
    for company in companies:
        snapshot = snapshots.get(company.id)
        regime = resolve_acessorias_regime(snapshot.regime_raw or snapshot.regime_code) if snapshot is not None else None
        tax_regime = regime.canonical if regime is not None and regime.canonical else (snapshot.regime_raw if snapshot is not None else None)
        is_simples = None if regime is None else _is_simples_regime(regime.canonical)
        is_mei = None if regime is None else (regime.canonical == FiscalRegime.MEI.value if regime.canonical else None)
        factor_r_result = get_company_factor_r_potential(session, company_id=company.id)
        factor_r_effective = effective_use_by_company_id.get(company.id)
        dominio_company_code = dominio_code_by_cnpj.get(_normalize_cnpj(company.cnpj))
        filter_action, reason = _resolve_filter_action(
            company=company,
            is_simples=is_simples,
            is_mei=is_mei,
            factor_r_result=factor_r_result,
            dominio_company_code=dominio_company_code,
        )
        rows.append(
            DominioFactorRTargetRow(
                dominio_company_code=dominio_company_code,
                company_cnpj=company.cnpj,
                company_name=company.razao_social,
                is_active=bool(company.active),
                tax_regime=tax_regime,
                is_mei=is_mei,
                factor_r_potential=factor_r_result.factor_r_potential,
                factor_r_effectively_used=factor_r_effective,
                factor_r_cnae_codes=tuple(factor_r_result.positive_cnaes),
                factor_r_reason=reason,
                filter_action=filter_action,
            )
        )

    ordered_rows = tuple(sorted(rows, key=_sort_key))
    target_payload = [
        {
            "dominio_company_code": row.dominio_company_code,
            "company_cnpj": _normalize_cnpj(row.company_cnpj),
        }
        for row in ordered_rows
        if row.filter_action == FILTER_ACTION_INCLUDE and row.dominio_company_code
    ]
    target_list_sha256 = hashlib.sha256(
        json.dumps(target_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    summary_payload = {
        "schema_version": 1,
        "organization_slug": organization.slug,
        "selection_scope": "FACTOR_R",
        "target_company_count": len(target_payload),
        "target_list_sha256": target_list_sha256,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return DominioFactorRTargetExport(
        organization_slug=organization.slug,
        rows=ordered_rows,
        target_company_count=len(target_payload),
        target_list_sha256=target_list_sha256,
        summary_payload=summary_payload,
    )


def build_factor_r_target_manifest_metadata(summary_payload: dict[str, object]) -> dict[str, object]:
    return {
        "selection_scope": "FACTOR_R",
        "source_filter_name": "Fator R",
        "target_company_count": summary_payload.get("target_company_count"),
        "target_list_sha256": normalize_target_list_sha256(summary_payload.get("target_list_sha256")),
    }


def _latest_snapshot_map(session: Session, *, organization_id: int, company_ids: Sequence[int]) -> dict[int, AcessoriasCompanySnapshot]:
    if not company_ids:
        return {}
    rows = session.scalars(
        select(AcessoriasCompanySnapshot)
        .where(
            AcessoriasCompanySnapshot.organization_id == organization_id,
            AcessoriasCompanySnapshot.company_id.in_(company_ids),
        )
        .order_by(AcessoriasCompanySnapshot.updated_at.desc(), AcessoriasCompanySnapshot.id.desc())
    ).all()
    result: dict[int, AcessoriasCompanySnapshot] = {}
    for row in rows:
        if row.company_id is not None and row.company_id not in result:
            result[row.company_id] = row
    return result


def _dominio_code_map(session: Session, *, organization_id: int, organization_slug: str) -> dict[str, str]:
    result = _latest_dominio_code_map(session, organization_id=organization_id)
    for normalized_cnpj, manual_code in get_manual_dominio_company_codes(organization_slug=organization_slug).items():
        if normalized_cnpj and manual_code:
            result.setdefault(normalized_cnpj, manual_code)
    return result


def _latest_dominio_code_map(session: Session, *, organization_id: int) -> dict[str, str]:
    rows = session.scalars(
        select(DominioPayrollCompanyMovement)
        .where(
            DominioPayrollCompanyMovement.organization_id == organization_id,
            DominioPayrollCompanyMovement.company_cnpj.is_not(None),
        )
        .order_by(DominioPayrollCompanyMovement.created_at.desc(), DominioPayrollCompanyMovement.id.desc())
    ).all()
    result: dict[str, str] = {}
    for row in rows:
        normalized_cnpj = _normalize_cnpj(row.company_cnpj)
        if not normalized_cnpj or normalized_cnpj in result:
            continue
        if row.dominio_company_code:
            result[normalized_cnpj] = row.dominio_company_code
    return result


def _factor_r_effective_use_map(session: Session, *, organization_id: int, company_ids: Sequence[int]) -> dict[int, bool | None]:
    if not company_ids:
        return {}
    rows = session.scalars(
        select(SittaxApuracaoSnapshot)
        .where(
            SittaxApuracaoSnapshot.organization_id == organization_id,
            SittaxApuracaoSnapshot.external_company_id.in_(company_ids),
        )
        .order_by(SittaxApuracaoSnapshot.last_seen_at.desc(), SittaxApuracaoSnapshot.id.desc())
    ).all()
    result: dict[int, bool | None] = {}
    for row in rows:
        if row.external_company_id is None or row.external_company_id in result:
            continue
        result[row.external_company_id] = row.factor_r_percent is not None
    return result


def _resolve_filter_action(
    *,
    company: ExternalCompany,
    is_simples: bool | None,
    is_mei: bool | None,
    factor_r_result: FactorRPotentialResult,
    dominio_company_code: str | None,
) -> tuple[str, str]:
    reasons: list[str] = []
    if not company.active:
        return FILTER_ACTION_REMOVE, "company_inactive"
    if is_simples is False:
        return FILTER_ACTION_REMOVE, "not_simples_nacional"
    if is_mei is True:
        return FILTER_ACTION_REMOVE, "mei_company"
    if factor_r_result.factor_r_potential is False:
        return FILTER_ACTION_REMOVE, "factor_r_not_applicable"
    if is_simples is None:
        reasons.append("regime_unknown")
    if is_mei is None:
        reasons.append("mei_status_unknown")
    if factor_r_result.factor_r_potential is None:
        reasons.append("factor_r_potential_unknown")
    if reasons:
        return FILTER_ACTION_REVIEW, ",".join(reasons)
    if not dominio_company_code:
        return FILTER_ACTION_MISSING_DOMINIO_CODE, "dominio_code_not_found"
    return FILTER_ACTION_INCLUDE, "simples_active_non_mei_factor_r_potential"


def _is_simples_regime(canonical: str | None) -> bool | None:
    if canonical is None:
        return None
    if canonical == FiscalRegime.SIMPLES_NACIONAL.value:
        return True
    if canonical == FiscalRegime.MEI.value:
        return False
    if canonical in {
        FiscalRegime.LUCRO_PRESUMIDO.value,
        FiscalRegime.LUCRO_REAL.value,
        FiscalRegime.IMUNE_ISENTA.value,
    }:
        return False
    return None


def _normalize_cnpj(value: str | None) -> str:
    if value is None:
        return ""
    return "".join(ch for ch in value if ch.isdigit())


def _sort_key(row: DominioFactorRTargetRow) -> tuple[int, str, str]:
    code = row.dominio_company_code or ""
    return (0 if code else 1, code, row.company_name.upper())


def _stringify_bool(value: bool) -> str:
    return "true" if value else "false"


def _stringify_optional_bool(value: bool | None) -> str:
    if value is None:
        return ""
    return _stringify_bool(value)
