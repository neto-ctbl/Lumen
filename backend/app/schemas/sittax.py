from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class SittaxOfficeReference(BaseModel):
    id: str
    name: str | None = None


class SittaxCompanyItem(BaseModel):
    external_id: str
    cnpj: str
    legal_name: str
    trade_name: str | None = None
    state_registration: str | None = None
    state: str | None = None
    status: str | None = None
    homologated: bool | None = None
    cash_regime: bool | None = None
    raw_payload: dict[str, Any] = Field(repr=False)


class SittaxApuracaoItem(BaseModel):
    requested_company_cnpj: str
    requested_period: str
    confirmed_company_cnpj: str | None = None
    confirmed_period: str
    apuracao_id: str
    office_name: str | None = None
    company_name: str | None = None
    is_transmitted: bool | None = None
    transmission_in_progress: bool | None = None
    das_number: str | None = None
    declaration_number: str | None = None
    statement_number: str | None = None
    transmission_type: str | None = None
    transmitted_at: str | None = None
    net_revenue: Decimal | None = None
    product_revenue: Decimal | None = None
    service_revenue: Decimal | None = None
    return_revenue: Decimal | None = None
    rbt12: Decimal | None = None
    rba: Decimal | None = None
    das_amount: Decimal | None = None
    das_xml_amount: Decimal | None = None
    factor_r_percent: Decimal | None = None
    company_has_payroll: bool | None = None
    taxes_icms: bool | None = None
    taxes_iss: bool | None = None
    taxes_ipi: bool | None = None
    taxes_pis_cofins: bool | None = None
    companies_apuracao: list[dict[str, Any]] = Field(default_factory=list)
    annexes: list[dict[str, Any]] = Field(default_factory=list)
    cfops: list[dict[str, Any]] = Field(default_factory=list)
    activities: list[dict[str, Any]] = Field(default_factory=list)
    payrolls: list[dict[str, Any]] = Field(default_factory=list)
    alerts: list[dict[str, Any] | str] = Field(default_factory=list)
    errors: list[dict[str, Any] | str] = Field(default_factory=list)
    risks: list[dict[str, Any] | str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(repr=False)
