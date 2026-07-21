from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class SittaxOfficeReference(BaseModel):
    id: str
    name: str | None = None
    cnpj: str | None = None


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


class SittaxDifalItem(BaseModel):
    difal_id: str
    has_guide: bool | None = None
    dare_numbers: list[str] = Field(default_factory=list)
    total_amount: Decimal | None = None
    resale_amount: Decimal | None = None
    use_consumption_fixed_asset_amount: Decimal | None = None
    total_purchases: Decimal | None = None
    closing_date: str | None = None
    transmission_date: str | None = None
    message: str | None = None
    notes_without_type_or_reference: bool | None = None
    inconsistencies: list[dict[str, Any] | str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(repr=False)


class SittaxFiscalDocumentItem(BaseModel):
    source_document_key: str
    sittax_document_id: str | None = None
    document_direction: str
    access_key: str | None = None
    model: str | None = None
    document_number: str | None = None
    status: str | None = None
    issue_date: str | None = None
    entry_date: str | None = None
    period_reference: str
    issuer_name: str | None = None
    issuer_state: str | None = None
    recipient_name: str | None = None
    recipient_state: str | None = None
    issuer_document: str | None = None
    cfops: list[str] = Field(default_factory=list)
    total_amount: Decimal | None = None
    import_source: str | None = None
    imported: bool | None = None
    has_xml: bool | None = None
    raw_payload: dict[str, Any] = Field(repr=False)


class SittaxFiscalDocumentPage(BaseModel):
    page_number: int
    page_size: int
    total: int | None = None
    total_filtered: int | None = None
    items: list[SittaxFiscalDocumentItem] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(repr=False)


class SittaxTaskItem(BaseModel):
    source_task_key: str
    sittax_task_id: str | None = None
    task_type: str | None = None
    task_name: str | None = None
    description: str | None = None
    company_name: str | None = None
    company_cnpj: str | None = None
    period_reference: str | None = None
    source_created_at: str | None = None
    source_finished_at: str | None = None
    source_user_id: str | None = None
    source_user_name: str | None = None
    status: str | None = None
    status_code: int | None = None
    has_file: bool | None = None
    file_name: str | None = None
    file_extension: str | None = None
    file_extension_code: int | None = None
    processing_time_seconds: Decimal | None = None
    raw_payload: dict[str, Any] = Field(repr=False)


class SittaxTaskPage(BaseModel):
    page_number: int
    page_size: int
    total: int | None = None
    total_filtered: int | None = None
    items: list[SittaxTaskItem] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(repr=False)
